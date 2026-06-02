#!/usr/bin/env bash
set -euo pipefail

APP_NAME="oracle-nl2sql"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OFFLINE_DIR="${REPO_ROOT}/deploy/rhel9/offline"
IMAGE_DIR="${OFFLINE_DIR}/images"
API_WHEEL_DIR="${OFFLINE_DIR}/wheels/api-py312-linux-amd64"
CONTAINER_ENGINE="${CONTAINER_ENGINE:-}"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif command -v python3.12 >/dev/null; then
  PYTHON_BIN="python3.12"
else
  echo "python3.12 is required." >&2
  exit 1
fi
PREPARE_IMAGES="${PREPARE_IMAGES:-1}"
PREPARE_API_WHEELS="${PREPARE_API_WHEELS:-1}"
BUILD_WEB_DIST="${BUILD_WEB_DIST:-1}"

PYTHON_BASE_IMAGE="docker.io/library/python:3.12"
PYTHON_BASE_TAR="${IMAGE_DIR}/python-3.12-linux-amd64.tar"
NGINX_BASE_IMAGE="docker.io/library/nginx:1.27-alpine"
NGINX_BASE_TAR="${IMAGE_DIR}/nginx-1.27-alpine-linux-amd64.tar"
QDRANT_IMAGE="docker.io/qdrant/qdrant:v1.12.4"
QDRANT_IMAGE_TAR="${IMAGE_DIR}/qdrant-v1.12.4-linux-amd64.tar"

if [[ "${PREPARE_IMAGES}" == "1" && -z "${CONTAINER_ENGINE}" ]]; then
  if command -v docker >/dev/null; then
    CONTAINER_ENGINE="docker"
  elif command -v podman >/dev/null; then
    CONTAINER_ENGINE="podman"
  else
    echo "docker or podman is required to prepare offline image tar files." >&2
    exit 1
  fi
fi

mkdir -p "${IMAGE_DIR}" "${API_WHEEL_DIR}"

save_image() {
  local image="$1"
  local target="$2"
  if [[ -f "${target}" ]]; then
    echo "Using existing ${target}"
    return
  fi

  echo "Pulling ${image} for linux/amd64"
  if [[ "${CONTAINER_ENGINE}" == "docker" ]]; then
    docker pull --platform linux/amd64 "${image}"
    docker save --platform linux/amd64 -o "${target}" "${image}"
  else
    podman pull --arch amd64 "${image}"
    podman save -o "${target}" "${image}"
  fi
}

if [[ "${PREPARE_IMAGES}" == "1" ]]; then
  echo "[1/4] Preparing linux/amd64 base/runtime image tar files"
  save_image "${PYTHON_BASE_IMAGE}" "${PYTHON_BASE_TAR}"
  save_image "${NGINX_BASE_IMAGE}" "${NGINX_BASE_TAR}"
  save_image "${QDRANT_IMAGE}" "${QDRANT_IMAGE_TAR}"
else
  echo "[1/4] Skipping image tar preparation"
fi

if [[ "${PREPARE_API_WHEELS}" == "1" ]]; then
  echo "[2/4] Downloading API Python packages for linux/amd64 Python 3.12"
  "${PYTHON_BIN}" "${REPO_ROOT}/deploy/rhel9/scripts/prepare-api-python-packages.py"
else
  echo "[2/4] Skipping API wheel download"
fi

if [[ "${BUILD_WEB_DIST}" == "1" ]]; then
  echo "[3/4] Building web dist"
  (
    cd "${REPO_ROOT}/apps/web"
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
    npm run build
  )
else
  echo "[3/4] Skipping web dist build"
fi

if [[ ! -f "${REPO_ROOT}/apps/web/dist/index.html" ]]; then
  echo "apps/web/dist/index.html is missing. Build the web app before creating the transfer archive." >&2
  exit 1
fi

echo "[4/4] Writing offline manifests"
rpm_count="$(find "${OFFLINE_DIR}/rpms" -maxdepth 1 -type f -name '*.rpm' 2>/dev/null | wc -l)"
host_wheel_count="$(find "${OFFLINE_DIR}/wheels/host-py312" -maxdepth 1 -type f -name '*.whl' 2>/dev/null | wc -l)"
api_wheel_count="$(find "${API_WHEEL_DIR}" -maxdepth 1 -type f -name '*.whl' | wc -l)"
image_count="$(find "${IMAGE_DIR}" -maxdepth 1 -type f -name '*.tar' | wc -l)"
cat > "${OFFLINE_DIR}/MANIFEST.txt" <<EOF
target_os=RHEL9-compatible
target_arch=x86_64
server_python=python3.12
rpm_count=${rpm_count}
host_wheel_count=${host_wheel_count}
api_wheel_count=${api_wheel_count}
image_tar_count=${image_count}
app_image_tar_count=$(find "${IMAGE_DIR}" -maxdepth 1 -type f -name "${APP_NAME}-*-linux-amd64.tar" | wc -l)
python_base_image_tar_count=$(find "${IMAGE_DIR}" -maxdepth 1 -type f -name 'python-3.12-linux-amd64.tar' | wc -l)
nginx_base_image_tar_count=$(find "${IMAGE_DIR}" -maxdepth 1 -type f -name 'nginx-1.27-alpine-linux-amd64.tar' | wc -l)
qdrant_image_tar_count=$(find "${IMAGE_DIR}" -maxdepth 1 -type f -name 'qdrant-v1.12.4-linux-amd64.tar' | wc -l)
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

(
  cd "${OFFLINE_DIR}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo "Offline build inputs are ready under ${OFFLINE_DIR}"
