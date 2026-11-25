#!/usr/bin/env bash
set -euo pipefail

# Enzonic Python Generic launcher. Use the same supervisor entry point as SillyDev.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$APP_DIR"

if [[ ! -f "${APP_DIR}/ashur_sillydev_start.py" ]]; then
  echo "ERROR: ASHUR supervisor launcher not found: ${APP_DIR}/ashur_sillydev_start.py"
  exit 1
fi

export PYTHONUNBUFFERED=1
export ASHUR_INTERVAL_SECONDS=300
exec python3 -u ashur_sillydev_start.py
