#!/usr/bin/env bash
set -euo pipefail

APP_NAME="oracle-nl2sql"
TARGET_ARCH="x86_64"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OFFLINE_DIR="${REPO_ROOT}/deploy/rhel9/offline"
DIST_DIR="${REPO_ROOT}/dist"
PROJECT_BUNDLE_DIR="${DIST_DIR}/${APP_NAME}-project-rhel9-${TARGET_ARCH}"
PROJECT_ARCHIVE="${PROJECT_BUNDLE_DIR}.tar.gz"
INSTALLER_PATH="${DIST_DIR}/install-${APP_NAME}-project-rhel9.sh"
ALLOW_INCOMPLETE_PROJECT_ARCHIVE="${ALLOW_INCOMPLETE_PROJECT_ARCHIVE:-0}"

required_paths=(
  "${OFFLINE_DIR}/rpms"
  "${OFFLINE_DIR}/wheels/api-py312-linux-amd64/.ready"
  "${REPO_ROOT}/apps/web/dist/index.html"
)

missing=()
for required_path in "${required_paths[@]}"; do
  if [[ ! -e "${required_path}" ]]; then
    missing+=("${required_path}")
  fi
done

if [[ "${#missing[@]}" -gt 0 ]]; then
  echo "Project transfer archive is missing offline build inputs:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  echo "Run deploy/rhel9/scripts/prepare-offline-build-inputs.sh before creating the archive." >&2
  if [[ "${ALLOW_INCOMPLETE_PROJECT_ARCHIVE}" != "1" ]]; then
    exit 1
  fi
  PROJECT_BUNDLE_DIR="${PROJECT_BUNDLE_DIR}-incomplete"
  PROJECT_ARCHIVE="${PROJECT_BUNDLE_DIR}.tar.gz"
  INSTALLER_PATH="${DIST_DIR}/install-${APP_NAME}-project-rhel9-incomplete.sh"
fi

rm -rf "${PROJECT_BUNDLE_DIR}" "${PROJECT_ARCHIVE}"
mkdir -p "${DIST_DIR}" "${PROJECT_BUNDLE_DIR}"

echo "[1/4] Copying project files"
tar \
  --exclude='./.git' \
  --exclude='./.env' \
  --exclude='./dist' \
  --exclude='./output' \
  --exclude='./apps/api/.venv' \
  --exclude='./apps/api/storage' \
  --exclude='./apps/web/node_modules' \
  --exclude='./apps/web/.vite' \
  --exclude='./apps/web/tsconfig.tsbuildinfo' \
  -C "${REPO_ROOT}" \
  -cf - . | tar -C "${PROJECT_BUNDLE_DIR}" -xf -

echo "[2/4] Preparing external installer"
cp "${REPO_ROOT}/deploy/rhel9/scripts/install-project-archive.sh" "${INSTALLER_PATH}"
chmod +x "${INSTALLER_PATH}"
find "${PROJECT_BUNDLE_DIR}/deploy/rhel9/scripts" -type f -name '*.sh' -exec chmod +x {} \;

echo "[3/4] Writing project bundle manifest"
cat > "${PROJECT_BUNDLE_DIR}/PROJECT_BUNDLE_MANIFEST.txt" <<EOF
${APP_NAME} project transfer archive
target_os=RHEL9-compatible
target_arch=${TARGET_ARCH}
server_python=python3.12
contains_source=1
contains_offline_rpms=$(test -d "${PROJECT_BUNDLE_DIR}/deploy/rhel9/offline/rpms" && echo 1 || echo 0)
contains_host_wheels=0
contains_api_wheelhouse=$(test -f "${PROJECT_BUNDLE_DIR}/deploy/rhel9/offline/wheels/api-py312-linux-amd64/.ready" && echo 1 || echo 0)
contains_base_images=0
contains_qdrant_image=$(test -f "${PROJECT_BUNDLE_DIR}/deploy/rhel9/offline/images/qdrant-v1.12.4-linux-amd64.tar" && echo 1 || echo 0)
contains_web_dist=$(test -f "${PROJECT_BUNDLE_DIR}/apps/web/dist/index.html" && echo 1 || echo 0)
runtime_mode=host-venv-systemd
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

(
  cd "${PROJECT_BUNDLE_DIR}"
  find . -type f ! -name PROJECT_BUNDLE_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > PROJECT_BUNDLE_SHA256SUMS
)

echo "[4/4] Creating project archive"
tar -C "${DIST_DIR}" -czf "${PROJECT_ARCHIVE}" "$(basename "${PROJECT_BUNDLE_DIR}")"

echo "Project archive ready: ${PROJECT_ARCHIVE}"
echo "External installer ready: ${INSTALLER_PATH}"
