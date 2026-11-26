#!/usr/bin/env python3
"""Keep the ASHUR daemon alive and restart it when its persisted heartbeat stalls."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAEMON = ROOT / "trading-lab" / "ashur_daemon.py"
DATA_DIR = Path(os.getenv("ASHUR_DATA_DIR", str(Path.home() / ".local" / "share" / "ashur")))
STATUS_FILE = DATA_DIR / "ashur_shadow_status.json"


def _int_setting(name, default, minimum=1):
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


HEARTBEAT_MAX_AGE_SECONDS = _int_setting("ASHUR_SUPERVISOR_MAX_HEARTBEAT_AGE", 900, 60)
STARTUP_GRACE_SECONDS = _int_setting("ASHUR_SUPERVISOR_STARTUP_GRACE", 300, 60)
CHECK_INTERVAL_SECONDS = _int_setting("ASHUR_SUPERVISOR_CHECK_INTERVAL", 30, 5)
RESTART_BACKOFF_SECONDS = _int_setting("ASHUR_SUPERVISOR_RESTART_BACKOFF", 15, 5)
MAX_RESTART_BACKOFF_SECONDS = _int_setting("ASHUR_SUPERVISOR_MAX_BACKOFF", 300, 15)


def heartbeat_age_seconds(status_file=STATUS_FILE, now=None):
    """Return heartbeat age, or None when the status file is missing/invalid."""
    try:
        data = json.loads(Path(status_file).read_text(encoding="utf-8"))
        stamp = data.get("updated_at")
        if not stamp:
            return None
        updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        age = (current - updated).total_seconds()
        if age < -60:
            return None
        return max(0.0, age)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def heartbeat_is_stale(age_seconds, process_uptime_seconds,
                       max_age_seconds=HEARTBEAT_MAX_AGE_SECONDS,
                       startup_grace_seconds=STARTUP_GRACE_SECONDS):
    """Avoid killing a freshly started daemon while still recovering its state."""
    if process_uptime_seconds < startup_grace_seconds:
        return False
    return age_seconds is None or age_seconds > max_age_seconds


def _log(message):
    print(f"{datetime.now(timezone.utc).isoformat()} ASHUR_SUPERVISOR {message}", flush=True)


def _stop_child(child):
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        _log("DAEMON_TERMINATE_TIMEOUT sending_kill=true")
        child.kill()
        child.wait(timeout=10)


def _backoff(restart_count):
    exponent = min(max(0, restart_count - 1), 5)
    return min(MAX_RESTART_BACKOFF_SECONDS, RESTART_BACKOFF_SECONDS * (2 ** exponent))


def run():
    if not DAEMON.is_file():
        raise SystemExit(f"ASHUR daemon file not found: {DAEMON}")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    restart_count = 0

    _log(
        f"START daemon={DAEMON} heartbeat_max_age={HEARTBEAT_MAX_AGE_SECONDS}s "
        f"startup_grace={STARTUP_GRACE_SECONDS}s check_interval={CHECK_INTERVAL_SECONDS}s"
    )

    # The dashboard is a separate read-only HTTP sidecar. It never shares the
    # trading worker connection and is optional when the host supplies no port.
    dashboard_server = None
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from dashboard.http_server import start_dashboard_server
        dashboard_server = start_dashboard_server(log=_log)
    except Exception as exc:
        _log(f"DASHBOARD_HTTP_INIT_FAILED reason={type(exc).__name__}")

    # History collection is an independent read-only sidecar. It writes only
    # dashboard history storage and never opens the trading worker database.
    history_collector = None
    try:
        from dashboard.history_store import start_history_collector
        history_collector = start_history_collector(log=_log)
    except Exception as exc:
        _log(f"DASHBOARD_HISTORY_INIT_FAILED reason={type(exc).__name__}")

    while True:
        started = time.monotonic()
        try:
            child = subprocess.Popen([sys.executable, str(DAEMON)], cwd=str(ROOT), env=env)
        except Exception as exc:
            restart_count += 1
            delay = _backoff(restart_count)
            _log(f"DAEMON_SPAWN_FAILED error={type(exc).__name__}:{exc} retry_in={delay}s")
            time.sleep(delay)
            continue

        _log(f"DAEMON_CHILD_STARTED pid={child.pid}")
        end_reason = "child_exited"

        while child.poll() is None:
            uptime = time.monotonic() - started
            age = heartbeat_age_seconds()
            if heartbeat_is_stale(age, uptime):
                end_reason = "heartbeat_stale"
                age_text = "missing_or_invalid" if age is None else f"{age:.0f}s"
                _log(f"HEARTBEAT_STALE age={age_text} uptime={uptime:.0f}s action=restart_child")
                _stop_child(child)
                break

            if uptime >= 1800 and age is not None and age <= HEARTBEAT_MAX_AGE_SECONDS:
                restart_count = 0

            time.sleep(CHECK_INTERVAL_SECONDS)

        return_code = child.poll()
        restart_count += 1
        delay = _backoff(restart_count)
        _log(f"DAEMON_CHILD_ENDED reason={end_reason} return_code={return_code} retry_in={delay}s")
        time.sleep(delay)


if __name__ == "__main__":
    run()
