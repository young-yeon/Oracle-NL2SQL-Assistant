#!/usr/bin/env bash
set -euo pipefail

APP_NAME="oracle-nl2sql"
APP_VERSION="${APP_VERSION:-0.1.0}"
OFFLINE_BUILD="${OFFLINE_BUILD:-1}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IMAGE_DIR="${REPO_ROOT}/deploy/rhel9/offline/images"
APP_IMAGE_TAR="${IMAGE_DIR}/${APP_NAME}-app-images-${APP_VERSION}-linux-amd64.tar"
PYTHON_BASE_IMAGE="docker.io/library/python:3.12"
PYTHON_BASE_TAR="${IMAGE_DIR}/python-3.12-linux-amd64.tar"
NGINX_BASE_IMAGE="docker.io/library/nginx:1.27-alpine"
NGINX_BASE_TAR="${IMAGE_DIR}/nginx-1.27-alpine-linux-amd64.tar"
QDRANT_IMAGE="docker.io/qdrant/qdrant:v1.12.4"
QDRANT_IMAGE_TAR="${IMAGE_DIR}/qdrant-v1.12.4-linux-amd64.tar"
API_WHEEL_DIR="${REPO_ROOT}/deploy/rhel9/offline/wheels/api-py312-linux-amd64"
WEB_DIST_DIR="${REPO_ROOT}/apps/web/dist"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This script must run on an x86_64 build host. Current arch: $(uname -m)" >&2
  exit 1
fi

command -v podman >/dev/null || { echo "podman is required." >&2; exit 1; }

mkdir -p "${IMAGE_DIR}"

if [[ "${OFFLINE_BUILD}" == "1" ]]; then
  for required_path in \
    "${PYTHON_BASE_TAR}" \
    "${NGINX_BASE_TAR}" \
    "${QDRANT_IMAGE_TAR}" \
    "${API_WHEEL_DIR}/.ready" \
    "${WEB_DIST_DIR}/index.html"
  do
    if [[ ! -e "${required_path}" ]]; then
      echo "Required offline build input not found: ${required_path}" >&2
      echo "Run deploy/rhel9/scripts/prepare-offline-build-inputs.sh before transferring the project." >&2
      exit 1
    fi
  done

  echo "[1/5] Loading offline base/runtime images"
  podman load -i "${PYTHON_BASE_TAR}"
  podman load -i "${NGINX_BASE_TAR}"
  podman load -i "${QDRANT_IMAGE_TAR}"

  echo "[2/5] Building API image offline"
  podman build \
    --pull=false \
    --network=none \
    -f "${REPO_ROOT}/apps/api/Dockerfile.offline" \
    -t "localhost/${APP_NAME}-api:${APP_VERSION}" \
    "${REPO_ROOT}"

  echo "[3/5] Building web image offline"
  podman build \
    --pull=false \
    --network=none \
    -f "${REPO_ROOT}/apps/web/Dockerfile.offline" \
    -t "localhost/${APP_NAME}-web:${APP_VERSION}" \
    "${REPO_ROOT}"

  echo "[4/5] Saving app image tar"
  podman save \
    -o "${APP_IMAGE_TAR}" \
    "localhost/${APP_NAME}-api:${APP_VERSION}" \
    "localhost/${APP_NAME}-web:${APP_VERSION}"

  echo "[5/5] Writing image checksums"
  (
    cd "${IMAGE_DIR}/.."
    find images -type f -name '*.tar' -print0 | sort -z | xargs -0 sha256sum > images.SHA256SUMS
  )

  echo "App image tar ready: ${APP_IMAGE_TAR}"
  echo "Qdrant image tar ready: ${QDRANT_IMAGE_TAR}"
  exit 0
fi

echo "[1/4] Building API image"
podman build \
  -f "${REPO_ROOT}/apps/api/Dockerfile" \
  -t "localhost/${APP_NAME}-api:${APP_VERSION}" \
  "${REPO_ROOT}"

echo "[2/4] Building web image"
podman build \
  -f "${REPO_ROOT}/apps/web/Dockerfile" \
  -t "localhost/${APP_NAME}-web:${APP_VERSION}" \
  "${REPO_ROOT}"

echo "[3/4] Ensuring offline Qdrant image tar"
if [[ -f "${QDRANT_IMAGE_TAR}" ]]; then
  echo "Using existing ${QDRANT_IMAGE_TAR}"
else
  podman pull "${QDRANT_IMAGE}"
  podman save -o "${QDRANT_IMAGE_TAR}" "${QDRANT_IMAGE}"
fi

echo "[4/4] Saving app image tar"
podman save \
  -o "${APP_IMAGE_TAR}" \
  "localhost/${APP_NAME}-api:${APP_VERSION}" \
  "localhost/${APP_NAME}-web:${APP_VERSION}"

(
  cd "${IMAGE_DIR}/.."
  find images -type f -name '*.tar' -print0 | sort -z | xargs -0 sha256sum > images.SHA256SUMS
)

echo "App image tar ready: ${APP_IMAGE_TAR}"
echo "Qdrant image tar ready: ${QDRANT_IMAGE_TAR}"
