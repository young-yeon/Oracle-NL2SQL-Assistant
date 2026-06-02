#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OFFLINE_DIR="${REPO_ROOT}/deploy/rhel9/offline"
RPM_DIR="${OFFLINE_DIR}/rpms"
API_WHEEL_DIR="${OFFLINE_DIR}/wheels/api-py312-linux-amd64"

mkdir -p "${RPM_DIR}" "${API_WHEEL_DIR}" "${OFFLINE_DIR}/images"

if ! command -v dnf >/dev/null; then
  echo "dnf is required to refresh Rocky/RHEL RPM artifacts." >&2
  exit 1
fi

if ! command -v python3.12 >/dev/null; then
  echo "python3.12 is required to refresh Python wheel artifacts." >&2
  exit 1
fi

echo "[1/3] Refreshing RHEL9-compatible x86_64 RPM files"
rm -f "${RPM_DIR}"/*.rpm
dnf --forcearch=x86_64 download --resolve --alldeps --destdir "${RPM_DIR}" \
  gcc \
  gcc-c++ \
  make \
  python3.12-devel \
  python3.12-pip \
  python3.12-setuptools \
  python3.12-wheel \
  glibc-devel \
  libstdc++-devel \
  binutils \
  kernel-headers
find "${RPM_DIR}" -name '*.i686.rpm' -delete

if [[ -n "${ORACLE_INSTANT_CLIENT_RPM_DIR:-}" ]]; then
  if [[ ! -d "${ORACLE_INSTANT_CLIENT_RPM_DIR}" ]]; then
    echo "ORACLE_INSTANT_CLIENT_RPM_DIR does not exist: ${ORACLE_INSTANT_CLIENT_RPM_DIR}" >&2
    exit 1
  fi
  find "${ORACLE_INSTANT_CLIENT_RPM_DIR}" -maxdepth 1 -type f -name '*.rpm' -exec cp {} "${RPM_DIR}/" \;
fi

echo "[2/3] Refreshing Python 3.12 x86_64 API wheelhouse"
python3.12 "${REPO_ROOT}/deploy/rhel9/scripts/prepare-api-python-packages.py"

echo "[3/3] Writing offline artifact checksums"
(
  cd "${OFFLINE_DIR}"
  find rpms wheels -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo "Offline RPM/WHL artifacts refreshed under ${OFFLINE_DIR}"
