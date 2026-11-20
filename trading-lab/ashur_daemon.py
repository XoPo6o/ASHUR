#!/usr/bin/env python3
"""Run the ASHUR paper worker every five minutes.

Runtime state is stored by the worker on the server's persistent filesystem.
The daemon deliberately does not commit or push SQLite/JSON state to GitHub.
"""
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "trading-lab" / "live_shadow_worker.py"
INTERVAL_SECONDS = max(30, int(os.environ.get("ASHUR_INTERVAL_SECONDS", "300")))


def log(message):
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"[{stamp}] {message}", flush=True)


def main():
    log(
        "ASHUR paper daemon started; "
        f"interval={INTERVAL_SECONDS}s; "
        f"python={sys.version.split()[0]}; "
        f"state_dir={os.environ.get('ASHUR_DATA_DIR', str(Path.home() / '.local/share/ashur'))}"
    )

    while True:
        started = time.monotonic()
        log("WORKER_CYCLE_START")
        try:
            env = os.environ.copy()
            env.setdefault("PYTHONUNBUFFERED", "1")
            result = subprocess.run(
                [sys.executable, str(WORKER)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=240,
            )
            for line in (result.stdout or "").splitlines():
                print(line, flush=True)
            log(f"WORKER_CYCLE_END exit_code={result.returncode}")
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout or b""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            for line in partial.splitlines():
                print(line, flush=True)
            log("WORKER_TIMEOUT after 240s; daemon remains alive for next cycle")
        except Exception as exc:
            log(f"WORKER_EXCEPTION {type(exc).__name__}: {exc}")
            for line in traceback.format_exc().strip().splitlines()[-8:]:
                log("TRACE " + line)

        elapsed = time.monotonic() - started
        delay = max(1, INTERVAL_SECONDS - elapsed)
        log(f"NEXT_CYCLE_IN {int(delay)}s")
        time.sleep(delay)


if __name__ == "__main__":
    main()
