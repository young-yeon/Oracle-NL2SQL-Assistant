#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-oracle-nl2sql}"

run_systemctl() {
  if [[ "${EUID}" -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

run_systemctl daemon-reload
run_systemctl restart "${SERVICE_NAME}"
run_systemctl status "${SERVICE_NAME}" --no-pager
