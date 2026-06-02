#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OFFLINE_DIR="${BUNDLE_DIR}/offline"
RPM_DIR="${OFFLINE_DIR}/rpms"
HOST_WHEEL_DIR="${OFFLINE_DIR}/wheels/host-py312"
ENV_EXAMPLE="${BUNDLE_DIR}/.env.example"
if [[ ! -f "${ENV_EXAMPLE}" && -f "${BUNDLE_DIR}/../../.env.example" ]]; then
  ENV_EXAMPLE="${BUNDLE_DIR}/../../.env.example"
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This setup is for x86_64 only. Current arch: $(uname -m)" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run install-host-prereqs.sh with sudo/root." >&2
  exit 1
fi

if [[ ! -d "${OFFLINE_DIR}" ]]; then
  echo "Offline files directory not found: ${OFFLINE_DIR}" >&2
  exit 1
fi

echo "[host 1/5] Installing RPM prerequisites"
mapfile -t rpm_files < <(find "${RPM_DIR}" -maxdepth 1 -type f \( -name '*.x86_64.rpm' -o -name '*.noarch.rpm' \) | sort)
if [[ "${#rpm_files[@]}" -eq 0 ]]; then
  echo "No x86_64/noarch RPM files found under ${RPM_DIR}" >&2
  exit 1
fi
dnf install -y --disablerepo='*' "${rpm_files[@]}"

echo "[host 2/5] Preparing optional Oracle Instant Client mount"
mkdir -p /opt/oracle
oracle_client_lib="$(find /usr/lib/oracle -type d -path '*/client64/lib' 2>/dev/null | sort -V | tail -n 1 || true)"
if [[ -n "${oracle_client_lib}" ]]; then
  ln -sfn "${oracle_client_lib}" /opt/oracle/instantclient
else
  mkdir -p /opt/oracle/instantclient
fi

echo "[host 3/5] Installing podman-compose from offline wheels"
if [[ ! -d "${HOST_WHEEL_DIR}" ]]; then
  echo "Host wheel directory not found: ${HOST_WHEEL_DIR}" >&2
  exit 1
fi
python3.12 -m pip install --no-index --find-links "${HOST_WHEEL_DIR}" podman-compose==1.5.0

echo "[host 4/5] Creating ${APP_HOME}"
mkdir -p "${APP_HOME}"
cp "${BUNDLE_DIR}/compose.yml" "${APP_HOME}/compose.yml"
if [[ ! -f "${ENV_EXAMPLE}" ]]; then
  echo ".env.example not found in bundle or project root." >&2
  exit 1
fi
cp "${ENV_EXAMPLE}" "${APP_HOME}/.env.example"
if [[ ! -f "${APP_HOME}/.env" ]]; then
  cp "${ENV_EXAMPLE}" "${APP_HOME}/.env"
fi

echo "[host 5/5] Installing helper scripts"
install -m 0755 "${BUNDLE_DIR}/scripts/deploy.sh" /usr/local/bin/oracle-nl2sql-deploy
install -m 0755 "${BUNDLE_DIR}/scripts/stop.sh" /usr/local/bin/oracle-nl2sql-stop
install -m 0755 "${BUNDLE_DIR}/scripts/smoke-test.sh" /usr/local/bin/oracle-nl2sql-smoke-test

echo "Host prerequisites are ready."
