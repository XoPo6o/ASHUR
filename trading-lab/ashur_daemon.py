#!/usr/bin/env python3
"""Run the ASHUR paper worker every five minutes and publish its paper ledger."""
import os
import subprocess
import shutil
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


def configure_github_push():
    """Prepare a persistent repo-scoped SSH deploy key for ledger publishing."""
    if not shutil.which("git"):
        log("LEDGER_AUTH_SETUP_ERROR git executable not found")
        return False
    if not shutil.which("ssh-keygen"):
        log("LEDGER_AUTH_SETUP_ERROR ssh-keygen executable not found")
        return False

    ssh_dir = Path.home() / ".ssh"
    key = ssh_dir / "id_ed25519_ashur"
    public_key = Path(str(key) + ".pub")
    known_hosts = ssh_dir / "known_hosts"

    try:
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(ssh_dir, 0o700)

        if not key.exists():
            generated = subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-C",
                 "ashur-enzonic-paper-worker", "-f", str(key)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            if generated.returncode:
                log("LEDGER_AUTH_SETUP_ERROR ssh-keygen: " + (generated.stdout or "").strip())
                return False
        os.chmod(key, 0o600)

        if not public_key.exists():
            derived = subprocess.run(
                ["ssh-keygen", "-y", "-f", str(key)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            if derived.returncode:
                log("LEDGER_AUTH_SETUP_ERROR cannot derive public key: " + (derived.stdout or "").strip())
                return False
            public_key.write_text(derived.stdout.strip() + " ashur-enzonic-paper-worker\n", encoding="utf-8")
        os.chmod(public_key, 0o644)

        if shutil.which("ssh-keyscan"):
            scan = subprocess.run(
                ["ssh-keyscan", "-H", "github.com"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15
            )
            if scan.returncode == 0 and scan.stdout.strip():
                existing = known_hosts.read_text(encoding="utf-8") if known_hosts.exists() else ""
                with known_hosts.open("a", encoding="utf-8") as handle:
                    for line in scan.stdout.splitlines():
                        if line and line not in existing:
                            handle.write(line + "\n")
                            existing += line + "\n"
                os.chmod(known_hosts, 0o600)

        os.environ["GIT_SSH_COMMAND"] = (
            "ssh -i " + str(key) +
            " -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
        )
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if remote.returncode == 0:
            set_remote = ["git", "remote", "set-url", "origin", "git@github.com:XoPo6o/ASHUR.git"]
        else:
            set_remote = ["git", "remote", "add", "origin", "git@github.com:XoPo6o/ASHUR.git"]
        configured = subprocess.run(
            set_remote, cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if configured.returncode:
            log("LEDGER_AUTH_SETUP_ERROR git remote: " + (configured.stdout or "").strip())
            return False

        log("GITHUB_DEPLOY_KEY_PUBLIC (add to XoPo6o/ASHUR -> Settings -> Deploy keys; enable Allow write access):")
        print(public_key.read_text(encoding="utf-8").strip(), flush=True)
        return True
    except Exception as exc:
        log("LEDGER_AUTH_SETUP_ERROR " + type(exc).__name__ + ": " + str(exc))
        return False


def main():
    log(f"ASHUR paper daemon started; interval={INTERVAL_SECONDS}s; branch={BRANCH}")
    configure_github_push()
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
