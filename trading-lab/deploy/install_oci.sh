#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/XoPo6o/ASHUR.git"
BRANCH="ashur-live-shadow"
APP_DIR="/opt/ashur"
SERVICE_SRC="${APP_DIR}/trading-lab/deploy/ashur-live-shadow.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with: sudo bash trading-lab/deploy/install_oci.sh"
  exit 1
fi

if ! grep -qi ubuntu /etc/os-release; then
  echo "This installer currently targets Ubuntu 22.04/24.04 on Oracle Cloud."
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip openssh-client

if ! id ashur >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /home/ashur --shell /bin/bash ashur
fi
mkdir -p /opt
chown ashur:ashur /opt

if [[ ! -d "${APP_DIR}/.git" ]]; then
  sudo -u ashur git clone --single-branch --branch "${BRANCH}" "${REPO}" "${APP_DIR}"
else
  sudo -u ashur git -C "${APP_DIR}" fetch origin "${BRANCH}"
  sudo -u ashur git -C "${APP_DIR}" checkout "${BRANCH}"
  sudo -u ashur git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
fi

sudo -u ashur python3 -m venv "${APP_DIR}/.venv"
sudo -u ashur "${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
sudo -u ashur "${APP_DIR}/.venv/bin/python" -m pip install pandas

install -d -o ashur -g ashur -m 700 /home/ashur/.ssh
if [[ ! -f /home/ashur/.ssh/id_ed25519 ]]; then
  sudo -u ashur ssh-keygen -t ed25519 -N "" -C "ashur-oci-paper-worker" -f /home/ashur/.ssh/id_ed25519
fi
ssh-keyscan -H github.com >> /home/ashur/.ssh/known_hosts 2>/dev/null || true
chown ashur:ashur /home/ashur/.ssh/known_hosts
chmod 600 /home/ashur/.ssh/known_hosts
cat > /home/ashur/.ssh/config <<'SSHCFG'
Host github.com
  HostName github.com
  User git
  IdentityFile /home/ashur/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking yes
SSHCFG
chown ashur:ashur /home/ashur/.ssh/config
chmod 600 /home/ashur/.ssh/config

sudo -u ashur git -C "${APP_DIR}" remote set-url origin git@github.com:XoPo6o/ASHUR.git
sudo -u ashur git -C "${APP_DIR}" config user.name "ASHUR OCI Paper Worker"
sudo -u ashur git -C "${APP_DIR}" config user.email "ashur-paper-worker@users.noreply.github.com"

install -m 644 "${SERVICE_SRC}" /etc/systemd/system/ashur-live-shadow.service
systemctl daemon-reload
systemctl enable --now ashur-live-shadow.service

echo
echo "ASHUR worker service installed and started."
echo "Add this PUBLIC deploy key to GitHub repo XoPo6o/ASHUR:"
echo "Settings -> Deploy keys -> Add deploy key -> Allow write access."
echo "----- BEGIN PUBLIC KEY -----"
cat /home/ashur/.ssh/id_ed25519.pub
echo "----- END PUBLIC KEY -----"
echo
echo "Check logs: sudo journalctl -u ashur-live-shadow -f"
echo "Check service: sudo systemctl status ashur-live-shadow"
echo "No exchange API keys are required; the worker uses public market data only."
