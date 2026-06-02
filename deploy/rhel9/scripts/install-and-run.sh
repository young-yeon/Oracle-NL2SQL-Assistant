#!/usr/bin/env bash
set -euo pipefail

APP_NAME="oracle-nl2sql"
APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
RUN_SMOKE_TEST="${RUN_SMOKE_TEST:-1}"
START_STACK="${START_STACK:-1}"
KEEP_EXTRACTED="${KEEP_EXTRACTED:-0}"

usage() {
  cat <<'EOF'
Usage:
  sudo ./install-oracle-nl2sql-rhel9.sh [bundle.tar.gz] [options]

Options:
  --app-home PATH       Install compose/env files under PATH. Default: /opt/oracle-nl2sql
  --env-file PATH       Copy this env file to APP_HOME/.env after install.
  --no-start            Install only; do not start the Podman stack.
  --no-smoke-test       Skip the health smoke test after start.
  --keep-extracted      Keep the temporary extracted bundle directory.
  -h, --help            Show this help.

Environment:
  APP_HOME              Same as --app-home.
  START_STACK=0         Same as --no-start.
  RUN_SMOKE_TEST=0      Same as --no-smoke-test.
EOF
}

archive_path=""
env_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-home)
      APP_HOME="${2:-}"
      shift 2
      ;;
    --env-file)
      env_file="${2:-}"
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
    --keep-extracted)
      KEEP_EXTRACTED=1
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
        echo "Only one bundle archive can be provided." >&2
        exit 1
      fi
      archive_path="$1"
      shift
      ;;
  esac
done

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

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bundle_dir=""
extract_dir=""

if [[ -z "${archive_path}" && -d "${script_dir}/../offline" ]]; then
  bundle_dir="$(cd "${script_dir}/.." && pwd)"
fi

if [[ -z "${archive_path}" && -z "${bundle_dir}" ]]; then
  mapfile -t candidates < <(find "$(pwd)" -maxdepth 1 -type f \( -name "${APP_NAME}-rhel9-x86_64.tar.gz" -o -name "${APP_NAME}-rhel9-x86_64.tgz" -o -name "${APP_NAME}-rhel9-x86_64.zip" \) | sort)
  if [[ "${#candidates[@]}" -eq 1 ]]; then
    archive_path="${candidates[0]}"
  elif [[ "${#candidates[@]}" -gt 1 ]]; then
    echo "Multiple bundle archives found. Pass one explicitly." >&2
    printf '  %s\n' "${candidates[@]}" >&2
    exit 1
  fi
fi

if [[ -n "${archive_path}" ]]; then
  if [[ ! -f "${archive_path}" ]]; then
    echo "Bundle archive not found: ${archive_path}" >&2
    exit 1
  fi
  extract_dir="$(mktemp -d /tmp/${APP_NAME}-install.XXXXXX)"
  case "${archive_path}" in
    *.tar.gz|*.tgz)
      tar -xzf "${archive_path}" -C "${extract_dir}"
      ;;
    *.zip)
      python3.12 - "${archive_path}" "${extract_dir}" <<'PY'
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
  mapfile -t extracted_dirs < <(find "${extract_dir}" -mindepth 1 -maxdepth 1 -type d | sort)
  if [[ "${#extracted_dirs[@]}" -ne 1 ]]; then
    echo "Expected exactly one top-level directory inside the bundle archive." >&2
    exit 1
  fi
  bundle_dir="${extracted_dirs[0]}"
fi

if [[ -z "${bundle_dir}" ]]; then
  echo "No bundle archive provided and this script is not inside an extracted bundle." >&2
  usage >&2
  exit 1
fi

cleanup() {
  if [[ "${KEEP_EXTRACTED}" != "1" && -n "${extract_dir}" && -d "${extract_dir}" ]]; then
    rm -rf "${extract_dir}"
  elif [[ "${KEEP_EXTRACTED}" == "1" && -n "${extract_dir}" ]]; then
    echo "Kept extracted bundle: ${extract_dir}"
  fi
}
trap cleanup EXIT

if [[ -n "${env_file}" && ! -f "${env_file}" ]]; then
  echo "Env file not found: ${env_file}" >&2
  exit 1
fi

echo "[1/4] Installing offline RPMs, wheels, images, and helper scripts"
APP_HOME="${APP_HOME}" bash "${bundle_dir}/scripts/install.sh"

if [[ -n "${env_file}" ]]; then
  echo "[2/4] Applying env file"
  cp "${env_file}" "${APP_HOME}/.env"
else
  echo "[2/4] Using ${APP_HOME}/.env"
fi

if [[ "${START_STACK}" == "1" ]]; then
  echo "[3/4] Starting Podman stack"
  APP_HOME="${APP_HOME}" bash "${bundle_dir}/scripts/deploy.sh"
else
  echo "[3/4] Skipping stack start"
fi

if [[ "${START_STACK}" == "1" && "${RUN_SMOKE_TEST}" == "1" ]]; then
  echo "[4/4] Running smoke test"
  "${bundle_dir}/scripts/smoke-test.sh"
else
  echo "[4/4] Skipping smoke test"
fi

echo "Done."
echo "Web: http://<server>:3000"
echo "API: http://<server>:8000"
