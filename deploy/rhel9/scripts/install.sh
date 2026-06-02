#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
APP_NAME="oracle-nl2sql"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OFFLINE_DIR="${BUNDLE_DIR}/offline"
IMAGE_DIR="${OFFLINE_DIR}/images"
QDRANT_IMAGE_TAR="${IMAGE_DIR}/qdrant-v1.12.4-linux-amd64.tar"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This bundle is for x86_64 only. Current arch: $(uname -m)" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run install.sh with sudo/root." >&2
  exit 1
fi

echo "[1/3] Preparing host"
APP_HOME="${APP_HOME}" bash "${SCRIPT_DIR}/install-host-prereqs.sh"

echo "[2/3] Loading container images"
mapfile -t image_tars < <(find "${IMAGE_DIR}" -maxdepth 1 -type f -name '*.tar' | sort)
if [[ "${#image_tars[@]}" -eq 0 ]]; then
  echo "No container image tar files found under ${IMAGE_DIR}" >&2
  echo "Add oracle-nl2sql linux/amd64 image tar files before installing on an offline server." >&2
  exit 1
fi
mapfile -t app_image_tars < <(find "${IMAGE_DIR}" -maxdepth 1 -type f -name "${APP_NAME}-*-linux-amd64.tar" | sort)
if [[ "${#app_image_tars[@]}" -eq 0 ]]; then
  echo "No ${APP_NAME} app image tar found under ${IMAGE_DIR}" >&2
  echo "Build it on an x86_64 host with deploy/rhel9/scripts/build-linux-amd64-images.sh before installing." >&2
  exit 1
fi
if [[ ! -f "${QDRANT_IMAGE_TAR}" ]]; then
  echo "Qdrant image tar not found: ${QDRANT_IMAGE_TAR}" >&2
  echo "The offline server cannot pull docker.io/qdrant/qdrant:v1.12.4, so this tar must be included." >&2
  exit 1
fi
for image_tar in "${image_tars[@]}"; do
  podman load -i "${image_tar}"
done

echo "[3/3] Install complete"
echo "Edit ${APP_HOME}/.env, then run: oracle-nl2sql-deploy"
