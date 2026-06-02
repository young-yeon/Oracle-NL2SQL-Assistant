#!/usr/bin/env bash
set -euo pipefail

APP_NAME="oracle-nl2sql"
APP_VERSION="${APP_VERSION:-0.1.0}"
TARGET_ARCH="x86_64"
ALLOW_INCOMPLETE_BUNDLE="${ALLOW_INCOMPLETE_BUNDLE:-0}"
INCLUDE_SOURCE_SNAPSHOT="${INCLUDE_SOURCE_SNAPSHOT:-0}"
bundle_complete=1
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DEPLOY_ROOT="${REPO_ROOT}/deploy/rhel9"
OFFLINE_DIR="${DEPLOY_ROOT}/offline"
DIST_DIR="${REPO_ROOT}/dist/${APP_NAME}-rhel9-${TARGET_ARCH}"
BOOTSTRAP_PATH="${REPO_ROOT}/dist/install-${APP_NAME}-rhel9.sh"
QDRANT_IMAGE_TAR="${OFFLINE_DIR}/images/qdrant-v1.12.4-linux-amd64.tar"

if [[ ! -d "${OFFLINE_DIR}/rpms" ]]; then
  echo "Offline RPM directory not found: ${OFFLINE_DIR}/rpms" >&2
  exit 1
fi

if [[ ! -d "${OFFLINE_DIR}/wheels/host-py312" ]]; then
  echo "Offline host wheel directory not found: ${OFFLINE_DIR}/wheels/host-py312" >&2
  exit 1
fi

app_image_count="$(find "${OFFLINE_DIR}/images" -maxdepth 1 -type f -name "${APP_NAME}-*-linux-amd64.tar" 2>/dev/null | wc -l)"
if [[ ! -f "${QDRANT_IMAGE_TAR}" ]]; then
  echo "Qdrant image tar not found: ${QDRANT_IMAGE_TAR}" >&2
  echo "The offline server cannot pull docker.io/qdrant/qdrant:v1.12.4." >&2
  if [[ "${ALLOW_INCOMPLETE_BUNDLE}" != "1" ]]; then
    exit 1
  fi
  bundle_complete=0
fi

if [[ "${app_image_count}" -eq 0 ]]; then
  echo "No ${APP_NAME} linux/amd64 app image tar found under ${OFFLINE_DIR}/images" >&2
  echo "Run deploy/rhel9/scripts/build-linux-amd64-images.sh on an x86_64 host first." >&2
  if [[ "${ALLOW_INCOMPLETE_BUNDLE}" != "1" ]]; then
    exit 1
  fi
  bundle_complete=0
fi

if [[ "${bundle_complete}" != "1" ]]; then
  DIST_DIR="${DIST_DIR}-incomplete"
  BOOTSTRAP_PATH="${REPO_ROOT}/dist/install-${APP_NAME}-rhel9-incomplete.sh"
fi

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}/scripts" "$(dirname "${BOOTSTRAP_PATH}")"

echo "[1/5] Copying deployment files"
cp "${REPO_ROOT}/.env.example" "${DIST_DIR}/.env.example"
cp "${DEPLOY_ROOT}/compose.yml" "${DIST_DIR}/compose.yml"
cp "${DEPLOY_ROOT}/README.md" "${DIST_DIR}/README.md"
for script_name in install.sh install-host-prereqs.sh deploy.sh stop.sh smoke-test.sh install-and-run.sh; do
  cp "${DEPLOY_ROOT}/scripts/${script_name}" "${DIST_DIR}/scripts/${script_name}"
done
chmod +x "${DIST_DIR}/scripts/"*.sh

echo "[2/5] Copying project-contained offline artifacts"
cp -a "${OFFLINE_DIR}" "${DIST_DIR}/offline"

echo "[3/5] Preparing one-shot installer"
cp "${DEPLOY_ROOT}/scripts/install-and-run.sh" "${BOOTSTRAP_PATH}"
chmod +x "${BOOTSTRAP_PATH}"

if [[ "${INCLUDE_SOURCE_SNAPSHOT}" == "1" ]]; then
  mkdir -p "${DIST_DIR}/app"
  tar \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='dist' \
    --exclude='node_modules' \
    --exclude='apps/web/dist' \
    --exclude='apps/api/.venv' \
    --exclude='apps/api/storage' \
    --exclude='deploy/rhel9/offline' \
    -C "${REPO_ROOT}" \
    -czf "${DIST_DIR}/app/source.tar.gz" .
fi

echo "[4/5] Writing manifest"
rpm_count="$(find "${DIST_DIR}/offline/rpms" -maxdepth 1 -type f -name '*.rpm' | wc -l)"
host_wheel_count="$(find "${DIST_DIR}/offline/wheels/host-py312" -maxdepth 1 -type f -name '*.whl' | wc -l)"
image_count="$(find "${DIST_DIR}/offline/images" -maxdepth 1 -type f -name '*.tar' | wc -l)"
dist_app_image_count="$(find "${DIST_DIR}/offline/images" -maxdepth 1 -type f -name "${APP_NAME}-*-linux-amd64.tar" | wc -l)"
qdrant_image_count="$(find "${DIST_DIR}/offline/images" -maxdepth 1 -type f -name 'qdrant-v1.12.4-linux-amd64.tar' | wc -l)"
cat > "${DIST_DIR}/MANIFEST.txt" <<EOF
${APP_NAME} ${APP_VERSION}
target_os=RHEL9-compatible
target_arch=${TARGET_ARCH}
server_python=python3.12
rpm_count=${rpm_count}
host_wheel_count=${host_wheel_count}
image_tar_count=${image_count}
app_image_tar_count=${dist_app_image_count}
qdrant_image_tar_count=${qdrant_image_count}
include_source_snapshot=${INCLUDE_SOURCE_SNAPSHOT}
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

(
  cd "${DIST_DIR}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo "[5/5] Creating archive"
tar -C "$(dirname "${DIST_DIR}")" -czf "${DIST_DIR}.tar.gz" "$(basename "${DIST_DIR}")"
echo "Bundle ready: ${DIST_DIR}"
echo "Archive ready: ${DIST_DIR}.tar.gz"
echo "One-shot installer ready: ${BOOTSTRAP_PATH}"
