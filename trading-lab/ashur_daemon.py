#!/usr/bin/env python3
"""Run the ASHUR paper worker every five minutes and publish its paper ledger."""
import os

# Enzonic may run as UID 999 without an /etc/passwd entry. Python libraries
# which resolve the login name must use these values instead of pwd.getpwuid().
for _name in ("USER", "LOGNAME", "LNAME", "USERNAME"):
    os.environ[_name] = "container"

import pwd
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "trading-lab" / "live_shadow_worker.py"
INTERVAL_SECONDS = int(os.environ.get("ASHUR_INTERVAL_SECONDS", "300"))
BRANCH = os.environ.get("ASHUR_GIT_BRANCH", "ashur-live-shadow")
REPOSITORY = "XoPo6o/ASHUR"
SSH_REMOTE = f"git@github.com:{REPOSITORY}.git"
HTTPS_REMOTE = f"https://github.com/{REPOSITORY}.git"
GITHUB_ED25519_HOST_KEY = (
    "github.com ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
)


def log(message):
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"[{stamp}] {message}", flush=True)


def log_exception(prefix, exc):
    log(f"{prefix} {type(exc).__name__}: {exc}")
    details = traceback.format_exc().strip().splitlines()
    for line in details[-8:]:
        log("TRACE " + line)


def git_config(key, value):
    result = subprocess.run(
        ["git", "config", "--local", key, value],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=15
    )
    if result.returncode:
        log("LEDGER_GIT_CONFIG_ERROR " + (result.stdout or "").strip())
        return False
    return True


def _push_result_ok(result):
    status = getattr(result, "ref_status", None)
    if status:
        rejected = {
            (ref.decode("utf-8", "replace") if isinstance(ref, bytes) else str(ref)):
            (message.decode("utf-8", "replace") if isinstance(message, bytes) else str(message))
            for ref, message in status.items() if message
        }
        if rejected:
            raise RuntimeError("GitHub rejected refs: " + repr(rejected))
    return result


def _push_with_paramiko(key):
    # IMPORTANT: Dulwich porcelain.push() does not expose the SSH vendor as a
    # supported transport kwarg. Configure Dulwich's actual vendor factory;
    # passing vendor=... to porcelain.push() is not a reliable override.
    import dulwich.client as dulwich_client
    from dulwich import porcelain
    from dulwich.contrib.paramiko_vendor import ParamikoSSHVendor

    dulwich_client.get_ssh_vendor = ParamikoSSHVendor
    log("LEDGER_ATTEMPT method=dulwich-paramiko host=github.com user=git")
    result = porcelain.push(
        str(ROOT),
        remote_location=SSH_REMOTE,
        refspecs=[f"HEAD:refs/heads/{BRANCH}"],
        username="git",
        key_filename=str(key),
        quiet=False,
    )
    return _push_result_ok(result)


def _push_with_https_token():
    token = (
        os.environ.get("ASHUR_GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    if not token:
        log("LEDGER_FALLBACK_SKIPPED method=https-token reason=no_token_env")
        return False

    from dulwich import porcelain

    log("LEDGER_ATTEMPT method=dulwich-https-token host=github.com")
    result = porcelain.push(
        str(ROOT),
        remote_location=HTTPS_REMOTE,
        refspecs=[f"HEAD:refs/heads/{BRANCH}"],
        username="x-access-token",
        password=token,
        quiet=False,
    )
    _push_result_ok(result)
    return True


def _push_with_openssh_if_uid_resolves():
    try:
        pwd.getpwuid(os.getuid())
    except KeyError:
        log(
            "LEDGER_FALLBACK_SKIPPED method=openssh-git "
            f"reason=uid_{os.getuid()}_missing_from_passwd"
        )
        return False

    key = Path.home() / ".ssh" / "id_ed25519_ashur"
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = (
        f"ssh -i {key} -o IdentitiesOnly=yes "
        f"-o UserKnownHostsFile={known_hosts} -o StrictHostKeyChecking=yes"
    )
    log("LEDGER_ATTEMPT method=git-openssh host=github.com")
    result = subprocess.run(
        ["git", "push", SSH_REMOTE, f"HEAD:refs/heads/{BRANCH}"],
        cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90
    )
    if result.stdout:
        for line in result.stdout.splitlines()[-12:]:
            log("GIT_PUSH " + line)
    if result.returncode:
        raise RuntimeError(f"git push exited {result.returncode}")
    return True


def publish_ledger():
    """Commit the local paper ledger and try independent push transports."""
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
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30
    )
    if add.returncode:
        log("LEDGER_STAGE_ERROR " + (add.stdout or "").strip())
        return

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT, timeout=30
    )
    if diff.returncode == 1:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        commit = subprocess.run(
            ["git", "commit", "-m", f"ASHUR paper ledger {stamp}"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=30
        )
        if commit.returncode:
            log("LEDGER_COMMIT_ERROR " + (commit.stdout or "").strip())
            return
        log("LEDGER_COMMIT_CREATED " + (commit.stdout or "").strip().splitlines()[-1])
    elif diff.returncode != 0:
        log("LEDGER_DIFF_ERROR unable_to_check_index")
        return
    else:
        log("LEDGER_NO_NEW_CHANGES")

    key = Path.home() / ".ssh" / "id_ed25519_ashur"
    failures = []

    # Attempt 1: pure-Python SSH transport; it does not invoke /usr/bin/ssh.
    try:
        _push_with_paramiko(key)
        log("LEDGER_PUBLISHED method=dulwich-paramiko branch=" + BRANCH)
        return
    except Exception as exc:
        failures.append("dulwich-paramiko=" + f"{type(exc).__name__}: {exc}")
        log_exception("LEDGER_ATTEMPT_FAILED method=dulwich-paramiko", exc)

    # Attempt 2: HTTPS Smart-Git protocol, when a token has been configured.
    try:
        if _push_with_https_token():
            log("LEDGER_PUBLISHED method=dulwich-https-token branch=" + BRANCH)
            return
    except Exception as exc:
        failures.append("dulwich-https-token=" + f"{type(exc).__name__}: {exc}")
        log_exception("LEDGER_ATTEMPT_FAILED method=dulwich-https-token", exc)

    # Attempt 3: native Git/OpenSSH, but only when this container's UID can be
    # resolved. On Enzonic UID 999 is currently unresolved, so don't repeat a
    # guaranteed failure every five minutes.
    try:
        if _push_with_openssh_if_uid_resolves():
            log("LEDGER_PUBLISHED method=git-openssh branch=" + BRANCH)
            return
    except Exception as exc:
        failures.append("git-openssh=" + f"{type(exc).__name__}: {exc}")
        log_exception("LEDGER_ATTEMPT_FAILED method=git-openssh", exc)

    log("LEDGER_PUBLISH_PENDING attempts=" + " | ".join(failures))


def configure_github_push():
    """Create a persistent Ed25519 key and configure a pinned GitHub host key."""
    if not shutil.which("git"):
        log("LEDGER_AUTH_SETUP_ERROR git executable not found")
        return False

    ssh_dir = Path.home() / ".ssh"
    key = ssh_dir / "id_ed25519_ashur"
    public_key = Path(str(key) + ".pub")
    known_hosts = ssh_dir / "known_hosts"

    try:
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(ssh_dir, 0o700)

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        if not key.exists():
            private_obj = Ed25519PrivateKey.generate()
            key.write_bytes(private_obj.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        else:
            private_obj = serialization.load_ssh_private_key(
                key.read_bytes(), password=None
            )
        os.chmod(key, 0o600)

        public_line = private_obj.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode("ascii")
        # Always derive the .pub file from the private key. This also repairs
        # the previous literal "\\n" suffix bug without rotating the key.
        public_key.write_text(
            public_line + " ashur-enzonic-paper-worker\n", encoding="utf-8"
        )
        os.chmod(public_key, 0o644)

        # Pin GitHub's published Ed25519 host key. Do not use accept-new.
        existing = known_hosts.read_text(encoding="utf-8") if known_hosts.exists() else ""
        if GITHUB_ED25519_HOST_KEY not in existing:
            known_hosts.write_text(
                existing.rstrip("\n") + ("\n" if existing else "")
                + GITHUB_ED25519_HOST_KEY + "\n",
                encoding="utf-8"
            )
        os.chmod(known_hosts, 0o600)

        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=15
        )
        set_remote = (
            ["git", "remote", "set-url", "origin", SSH_REMOTE]
            if remote.returncode == 0
            else ["git", "remote", "add", "origin", SSH_REMOTE]
        )
        configured = subprocess.run(
            set_remote, cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15
        )
        if configured.returncode:
            log("LEDGER_AUTH_SETUP_ERROR git remote: " + (configured.stdout or "").strip())
            return False

        try:
            pwd.getpwuid(os.getuid())
            passwd_state = "resolved"
        except KeyError:
            passwd_state = "missing"
        log(
            "LEDGER_AUTH_READY "
            f"uid={os.getuid()} passwd={passwd_state} "
            f"home={Path.home()} ssh_binary={bool(shutil.which('ssh'))} "
            f"token_fallback={bool(os.environ.get('ASHUR_GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'))}"
        )
        log("GITHUB_DEPLOY_KEY_PUBLIC (must match the repository Deploy Key with write access):")
        print(public_key.read_text(encoding="utf-8").strip(), flush=True)
        return True
    except Exception as exc:
        log_exception("LEDGER_AUTH_SETUP_ERROR", exc)
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
            log_exception("WORKER_EXCEPTION", exc)

        elapsed = time.monotonic() - started
        delay = max(1, INTERVAL_SECONDS - elapsed)
        log(f"NEXT_CYCLE_IN {int(delay)}s")
        time.sleep(delay)


if __name__ == "__main__":
    main()
