#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-oracle-nl2sql}"

if [[ "${EUID}" -eq 0 ]]; then
  systemctl stop "${SERVICE_NAME}"
else
  sudo systemctl stop "${SERVICE_NAME}"
fi
