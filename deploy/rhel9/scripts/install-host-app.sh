#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-oracle-nl2sql}"
API_PORT="${API_PORT:-8000}"

OFFLINE_DIR="${PROJECT_ROOT}/deploy/rhel9/offline"
API_PACKAGE_DIR="${OFFLINE_DIR}/wheels/api-py312-linux-amd64"
VENV_DIR="${APP_HOME}/.venv"
ENV_FILE="${APP_HOME}/.env"
STORAGE_DIR="${APP_HOME}/storage"
LOG_DIR="${APP_HOME}/logs"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This installer is for x86_64 only. Current arch: $(uname -m)" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run install-host-app.sh with sudo/root." >&2
  exit 1
fi

for required_path in \
  "${API_PACKAGE_DIR}/.ready" \
  "${PROJECT_ROOT}/apps/api/requirements.txt" \
  "${PROJECT_ROOT}/apps/api/app" \
  "${PROJECT_ROOT}/apps/web/dist/index.html" \
  "${PROJECT_ROOT}/configs/guardrails"
do
  if [[ ! -e "${required_path}" ]]; then
    echo "Required host deployment input not found: ${required_path}" >&2
    exit 1
  fi
done

echo "[app 1/5] Creating application directories"
mkdir -p "${APP_HOME}" "${STORAGE_DIR}" "${LOG_DIR}"
cp "${PROJECT_ROOT}/.env.example" "${APP_HOME}/.env.example"
if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${PROJECT_ROOT}/.env.example" "${ENV_FILE}"
fi

echo "[app 2/5] Writing host runtime env"
cat > "${APP_HOME}/host.env" <<EOF
APP_ENV=production
PYTHONPATH=${PROJECT_ROOT}/apps/api
STORAGE_DIR=${STORAGE_DIR}
WEB_DIST_DIR=${PROJECT_ROOT}/apps/web/dist
NEMO_CONFIG_PATH=${PROJECT_ROOT}/configs/guardrails
CORS_ORIGINS=http://localhost:${API_PORT},http://127.0.0.1:${API_PORT}
EOF

echo "[app 3/5] Creating Python virtual environment"
python3.12 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" - <<'PY'
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Expected Python 3.12 venv, got {sys.version}")
PY
"${VENV_DIR}/bin/python" -m pip install --no-index --find-links "${API_PACKAGE_DIR}" setuptools wheel
"${VENV_DIR}/bin/python" -m pip install \
  --no-index \
  --find-links "${API_PACKAGE_DIR}" \
  --no-build-isolation \
  -r "${PROJECT_ROOT}/apps/api/requirements.txt"

echo "[app 4/5] Installing systemd service"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Oracle NL2SQL Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_ROOT}
EnvironmentFile=-${ENV_FILE}
EnvironmentFile=${APP_HOME}/host.env
ExecStart=${VENV_DIR}/bin/uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "[app 5/5] Starting service"
systemctl enable --now "${SERVICE_NAME}"
systemctl status "${SERVICE_NAME}" --no-pager || true

echo "Host app service installed."
echo "Web/API: http://<server>:${API_PORT}"
