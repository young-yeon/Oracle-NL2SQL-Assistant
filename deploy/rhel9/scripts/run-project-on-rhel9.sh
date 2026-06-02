#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
START_STACK="${START_STACK:-1}"
RUN_SMOKE_TEST="${RUN_SMOKE_TEST:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This runner is for x86_64 only. Current arch: $(uname -m)" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run run-project-on-rhel9.sh with sudo/root." >&2
  exit 1
fi

command -v python3.12 >/dev/null || {
  echo "python3.12 is required. Install it first: sudo dnf install python3.12" >&2
  exit 1
}

echo "[1/3] Installing host prerequisites"
APP_HOME="${APP_HOME}" bash "${PROJECT_ROOT}/deploy/rhel9/scripts/install-host-prereqs.sh"

if [[ "${START_STACK}" == "1" ]]; then
  echo "[2/3] Installing and starting host app service"
  APP_HOME="${APP_HOME}" PROJECT_ROOT="${PROJECT_ROOT}" bash "${PROJECT_ROOT}/deploy/rhel9/scripts/install-host-app.sh"
else
  echo "[2/3] Skipping host app start"
fi

if [[ "${START_STACK}" == "1" && "${RUN_SMOKE_TEST}" == "1" ]]; then
  echo "[3/3] Running smoke test"
  API_BASE="http://127.0.0.1:8000" WEB_BASE="http://127.0.0.1:8000" "${PROJECT_ROOT}/deploy/rhel9/scripts/smoke-test.sh"
else
  echo "[3/3] Skipping smoke test"
fi

echo "Done."
echo "Web: http://<server>:8000"
echo "API: http://<server>:8000"
