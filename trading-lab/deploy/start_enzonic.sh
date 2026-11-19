#!/usr/bin/env bash
set -euo pipefail

# Enzonic Python Generic persistent-worker launcher for ASHUR.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH_DIR="${HOME}/.ssh"
KEY="${SSH_DIR}/id_ed25519"

if [[ ! -f "${APP_DIR}/trading-lab/ashur_daemon.py" ]]; then
  echo "ERROR: ASHUR daemon not found under ${APP_DIR}/trading-lab."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required but is not installed in this Python Generic image."
  exit 1
fi

if ! command -v ssh-keygen >/dev/null 2>&1; then
  echo "ERROR: ssh-keygen is required to publish the paper ledger to GitHub."
  exit 1
fi

mkdir -p "${SSH_DIR}"
chmod 700 "${SSH_DIR}"

if [[ ! -f "${KEY}" ]]; then
  ssh-keygen -t ed25519 -N "" -C "ashur-enzonic-paper-worker" -f "${KEY}"
fi
chmod 600 "${KEY}"
chmod 644 "${KEY}.pub"

# Trust GitHub's SSH host key and use this server's repo-scoped deploy key.
touch "${SSH_DIR}/known_hosts"
ssh-keyscan -H github.com >> "${SSH_DIR}/known_hosts" 2>/dev/null || true
chmod 600 "${SSH_DIR}/known_hosts"

export GIT_SSH_COMMAND="ssh -i ${KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
git -C "${APP_DIR}" remote set-url origin git@github.com:XoPo6o/ASHUR.git
git -C "${APP_DIR}" config --local user.name "ASHUR Enzonic Paper Worker"
git -C "${APP_DIR}" config --local user.email "ashur-enzonic-paper-worker@users.noreply.github.com"

echo "ASHUR Enzonic launcher ready."
echo "Add this PUBLIC key to GitHub: XoPo6o/ASHUR -> Settings -> Deploy keys -> Add deploy key."
echo "Enable Allow write access. This is a public key; do not share the private id_ed25519 file."
cat "${KEY}.pub"
echo "Starting six-strategy paper daemon; interval=300s; branch=ashur-live-shadow."

export PYTHONUNBUFFERED=1
export ASHUR_INTERVAL_SECONDS=300
export ASHUR_GIT_BRANCH=ashur-live-shadow
cd "${APP_DIR}"
exec python3 -u trading-lab/ashur_daemon.py
