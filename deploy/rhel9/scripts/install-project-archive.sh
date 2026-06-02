#!/usr/bin/env bash
set -euo pipefail

APP_NAME="oracle-nl2sql"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/oracle-nl2sql-project}"
APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
KEEP_EXTRACTED="${KEEP_EXTRACTED:-1}"
START_STACK="${START_STACK:-1}"
RUN_SMOKE_TEST="${RUN_SMOKE_TEST:-1}"

usage() {
  cat <<'EOF'
Usage:
  sudo bash install-oracle-nl2sql-project-rhel9.sh oracle-nl2sql-project-rhel9-x86_64.tar.gz [options]

Options:
  --install-root PATH   Extract project under PATH. Default: /opt/oracle-nl2sql-project
  --app-home PATH       Install compose/env files under PATH. Default: /opt/oracle-nl2sql
  --no-start            Build/install only; do not start the Podman stack.
  --no-smoke-test       Skip smoke test after start.
  -h, --help            Show this help.

The target server must already have python3.12 installed.
EOF
}

archive_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root)
      INSTALL_ROOT="${2:-}"
      shift 2
      ;;
    --app-home)
      APP_HOME="${2:-}"
      shift 2
      ;;
    --no-start)
      START_STACK=0
      shift
      ;;
    --no-smoke-test)
      RUN_SMOKE_TEST=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [[ -n "${archive_path}" ]]; then
        echo "Only one project archive can be provided." >&2
        exit 1
      fi
      archive_path="$1"
      shift
      ;;
  esac
done

if [[ -z "${archive_path}" ]]; then
  echo "Project archive is required." >&2
  usage >&2
  exit 1
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "This installer is for x86_64 only. Current arch: $(uname -m)" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo/root." >&2
  exit 1
fi

command -v python3.12 >/dev/null || {
  echo "python3.12 is required. Install it first: sudo dnf install python3.12" >&2
  exit 1
}

if [[ ! -f "${archive_path}" ]]; then
  echo "Project archive not found: ${archive_path}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d /tmp/${APP_NAME}-project.XXXXXX)"
cleanup() {
  if [[ "${KEEP_EXTRACTED}" != "1" && -d "${tmp_dir}" ]]; then
    rm -rf "${tmp_dir}"
  fi
}
trap cleanup EXIT

echo "[1/3] Extracting project archive"
case "${archive_path}" in
  *.tar.gz|*.tgz)
    tar -xzf "${archive_path}" -C "${tmp_dir}"
    ;;
  *.zip)
    python3.12 - "${archive_path}" "${tmp_dir}" <<'PY'
import sys
import zipfile

archive, target = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(archive) as zf:
    zf.extractall(target)
PY
    ;;
  *)
    echo "Unsupported archive type: ${archive_path}" >&2
    exit 1
    ;;
esac

mapfile -t extracted_dirs < <(find "${tmp_dir}" -mindepth 1 -maxdepth 1 -type d | sort)
if [[ "${#extracted_dirs[@]}" -ne 1 ]]; then
  echo "Expected exactly one top-level directory inside the project archive." >&2
  exit 1
fi

echo "[2/3] Installing project under ${INSTALL_ROOT}"
rm -rf "${INSTALL_ROOT}"
mkdir -p "$(dirname "${INSTALL_ROOT}")"
mv "${extracted_dirs[0]}" "${INSTALL_ROOT}"

echo "[3/3] Building and running project"
APP_HOME="${APP_HOME}" \
START_STACK="${START_STACK}" \
RUN_SMOKE_TEST="${RUN_SMOKE_TEST}" \
  bash "${INSTALL_ROOT}/deploy/rhel9/scripts/run-project-on-rhel9.sh"

echo "Project installed at ${INSTALL_ROOT}"
