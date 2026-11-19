#!/usr/bin/env python3
"""Run the ASHUR paper worker every five minutes and publish its paper ledger."""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "trading-lab" / "live_shadow_worker.py"
INTERVAL_SECONDS = int(os.environ.get("ASHUR_INTERVAL_SECONDS", "300"))
BRANCH = os.environ.get("ASHUR_GIT_BRANCH", "ashur-live-shadow")


def log(message):
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"[{stamp}] {message}", flush=True)


def git_config(key, value):
    result = subprocess.run(
        ["git", "config", "--local", key, value],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    if result.returncode:
        log("LEDGER_GIT_CONFIG_ERROR " + (result.stdout or "").strip())
        return False
    return True


def publish_ledger():
    # Give Git a deterministic identity inside this clone; no global account
    # settings or personal identity are needed for automated paper-ledger commits.
    if not git_config("user.name", "ASHUR Paper Bot"):
        return
    if not git_config("user.email", "ashur-paper-bot@users.noreply.github.com"):
        return

    files = [
        "trading-lab/ashur_shadow.db",
        "trading-lab/ashur_shadow_status.json",
    ]
    add = subprocess.run(
        ["git", "add", "-f", *files], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if add.returncode:
        log("LEDGER_STAGE_ERROR " + (add.stdout or "").strip())
        return
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT
    )
    if diff.returncode == 1:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        commit = subprocess.run(
            ["git", "commit", "-m", f"ASHUR paper ledger {stamp}"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        if commit.returncode:
            log("LEDGER_COMMIT_ERROR " + (commit.stdout or "").strip())
            return
    elif diff.returncode != 0:
        log("LEDGER_DIFF_ERROR")
        return

    push = subprocess.run(
        ["git", "push", "origin", f"HEAD:refs/heads/{BRANCH}"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    if push.returncode:
        log("LEDGER_PUBLISH_PENDING " + (push.stdout or "").strip())
    else:
        log("LEDGER_PUBLISHED to " + BRANCH)


def main():
    log(f"ASHUR paper daemon started; interval={INTERVAL_SECONDS}s; branch={BRANCH}")
    while True:
        started = time.monotonic()
        log("WORKER_CYCLE_START")
        try:
            result = subprocess.run(
                [sys.executable, str(WORKER)],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=240
            )
            for line in (result.stdout or "").splitlines():
                print(line, flush=True)
            log(f"WORKER_CYCLE_END exit_code={result.returncode}")
            if result.returncode == 0:
                publish_ledger()
        except subprocess.TimeoutExpired:
            log("WORKER_TIMEOUT after 240s; system remains alive for next cycle")
        except Exception as exc:
            log(f"WORKER_EXCEPTION {type(exc).__name__}: {exc}")

        elapsed = time.monotonic() - started
        delay = max(1, INTERVAL_SECONDS - elapsed)
        log(f"NEXT_CYCLE_IN {int(delay)}s")
        time.sleep(delay)


if __name__ == "__main__":
    main()
