#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OFFLINE_DIR="${BUNDLE_DIR}/offline"
RPM_DIR="${OFFLINE_DIR}/rpms"
API_PACKAGE_DIR="${OFFLINE_DIR}/wheels/api-py312-linux-amd64"
ENV_EXAMPLE="${BUNDLE_DIR}/.env.example"
if [[ ! -f "${ENV_EXAMPLE}" && -f "${BUNDLE_DIR}/../../.env.example" ]]; then
  ENV_EXAMPLE="${BUNDLE_DIR}/../../.env.example"
fi
INSTALL_OFFLINE_BUILD_RPMS="${INSTALL_OFFLINE_BUILD_RPMS:-0}"

PIP_RPM_PATTERNS=(
  "python3.12-pip-*.noarch.rpm"
  "python3.12-pip-wheel-*.noarch.rpm"
  "python3.12-setuptools-*.noarch.rpm"
  "python3.12-wheel-*.noarch.rpm"
)

BUILD_RPM_PATTERNS=(
  "binutils-[0-9]*.x86_64.rpm"
  "cpp-*.x86_64.rpm"
  "gcc-[0-9]*.x86_64.rpm"
  "gcc-c++-*.x86_64.rpm"
  "glibc-devel-*.x86_64.rpm"
  "glibc-headers-*.x86_64.rpm"
  "kernel-headers-*.x86_64.rpm"
  "libgomp-*.x86_64.rpm"
  "libmpc-*.x86_64.rpm"
  "libstdc++-devel-*.x86_64.rpm"
  "libxcrypt-devel-*.x86_64.rpm"
  "make-*.x86_64.rpm"
  "python3.12-devel-*.x86_64.rpm"
)

PROTECTED_RPM_PATTERNS=(
  "systemd-*.rpm"
  "systemd-libs-*.rpm"
  "systemd-pam-*.rpm"
  "systemd-rpm-macros-*.rpm"
  "bash-*.rpm"
  "coreutils-*.rpm"
  "filesystem-*.rpm"
  "setup-*.rpm"
  "glibc-[0-9]*.rpm"
  "glibc-common-*.rpm"
  "glibc-gconv-extra-*.rpm"
  "glibc-minimal-langpack-*.rpm"
  "rpm-[0-9]*.rpm"
  "rpm-libs-*.rpm"
)

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

command -v python3.12 >/dev/null || {
  echo "python3.12 is required. Install it first: sudo dnf install python3.12" >&2
  exit 1
}

rpm_matches_protected_pattern() {
  local rpm_path="$1"
  local rpm_name
  rpm_name="$(basename "${rpm_path}")"
  local pattern
  for pattern in "${PROTECTED_RPM_PATTERNS[@]}"; do
    if [[ "${rpm_name}" == ${pattern} ]]; then
      return 0
    fi
  done
  return 1
}

collect_rpms_by_patterns() {
  local -n output_ref="$1"
  shift
  output_ref=()

  if [[ ! -d "${RPM_DIR}" ]]; then
    return 0
  fi

  local pattern rpm_path
  for pattern in "$@"; do
    while IFS= read -r rpm_path; do
      if rpm_matches_protected_pattern "${rpm_path}"; then
        echo "Skipping protected/core RPM candidate: $(basename "${rpm_path}")"
        continue
      fi
      output_ref+=("${rpm_path}")
    done < <(find "${RPM_DIR}" -maxdepth 1 -type f -name "${pattern}" | sort)
  done
}

install_selected_rpms() {
  local reason="$1"
  shift
  local rpm_files=("$@")

  if [[ "${#rpm_files[@]}" -eq 0 ]]; then
    echo "No offline RPM files selected for ${reason}."
    return 0
  fi

  echo "Installing ${#rpm_files[@]} offline RPM(s) for ${reason}."
  if ! dnf install -y --disablerepo='*' --setopt=install_weak_deps=False "${rpm_files[@]}"; then
    cat >&2 <<EOF
Offline RPM installation failed while preparing ${reason}.

The installer intentionally avoids installing the whole RPM bundle because that
can cause dnf to replace or remove protected RHEL packages such as systemd.

On a strict RHEL server, use RPMs from the same RHEL minor release/media for
these packages, or preinstall them before rerunning this script:
  python3.12-pip python3.12-devel gcc gcc-c++ make
EOF
    exit 1
  fi
}

venv_with_pip_ready() {
  local tmp_dir
  tmp_dir="$(mktemp -d /tmp/oracle-nl2sql-venv-check.XXXXXX)"
  if python3.12 -m venv "${tmp_dir}/venv" >/dev/null 2>&1 \
    && "${tmp_dir}/venv/bin/python" -m pip --version >/dev/null 2>&1; then
    rm -rf "${tmp_dir}"
    return 0
  fi
  rm -rf "${tmp_dir}"
  return 1
}

source_python_packages_present() {
  [[ -d "${API_PACKAGE_DIR}" ]] || return 1
  find "${API_PACKAGE_DIR}" -maxdepth 1 -type f \( -name '*.tar.gz' -o -name '*.zip' \) -print -quit | grep -q .
}

build_tools_ready() {
  command -v gcc >/dev/null || return 1
  if ! command -v g++ >/dev/null && ! command -v c++ >/dev/null; then
    return 1
  fi
  command -v make >/dev/null || return 1
  command -v python3.12-config >/dev/null || return 1
  python3.12 - <<'PY'
import pathlib
import sys
import sysconfig

include_dir = pathlib.Path(sysconfig.get_paths()["include"])
if not (include_dir / "Python.h").exists():
    raise SystemExit(1)
PY
}

echo "[host 1/5] Checking Python 3.12 venv support"
if ! venv_with_pip_ready; then
  echo "python3.12 venv/pip is not ready; trying offline pip support RPMs."
  pip_rpms=()
  collect_rpms_by_patterns pip_rpms "${PIP_RPM_PATTERNS[@]}"
  install_selected_rpms "Python 3.12 pip/venv support" "${pip_rpms[@]}"
fi

if ! venv_with_pip_ready; then
  cat >&2 <<'EOF'
python3.12 is installed, but it cannot create a venv with pip.
Install the matching RHEL9 python3.12-pip package, then rerun this script.
EOF
  exit 1
fi

echo "[host 2/5] Checking Python source build prerequisites"
if source_python_packages_present; then
  if build_tools_ready; then
    echo "Build tools are ready."
  elif [[ "${INSTALL_OFFLINE_BUILD_RPMS}" == "0" ]]; then
    cat >&2 <<'EOF'
The offline Python packagehouse contains source packages, but build tools are
not available. Refresh the API wheelhouse so it contains only wheels, or install
matching RHEL9 python3.12-devel gcc gcc-c++ make packages and rerun with
INSTALL_OFFLINE_BUILD_RPMS=1.
EOF
    exit 1
  else
    echo "Source packages found; trying minimal offline build-tool RPMs."
    build_rpms=()
    collect_rpms_by_patterns build_rpms "${BUILD_RPM_PATTERNS[@]}"
    install_selected_rpms "Python source package builds" "${build_rpms[@]}"
    if ! build_tools_ready; then
      cat >&2 <<'EOF'
Build tools are still incomplete after installing the minimal offline RPM set.
Install matching RHEL9 python3.12-devel gcc gcc-c++ make packages, then rerun.
EOF
      exit 1
    fi
  fi
else
  echo "No source Python packages found in the API packagehouse."
fi

echo "[host 3/5] Preparing optional Oracle Instant Client mount"
mkdir -p /opt/oracle
oracle_client_lib="$(find /usr/lib/oracle -type d -path '*/client64/lib' 2>/dev/null | sort -V | tail -n 1 || true)"
if [[ -n "${oracle_client_lib}" ]]; then
  ln -sfn "${oracle_client_lib}" /opt/oracle/instantclient
else
  mkdir -p /opt/oracle/instantclient
fi

echo "[host 4/5] Creating ${APP_HOME}"
mkdir -p "${APP_HOME}"
if [[ -f "${BUNDLE_DIR}/compose.yml" ]]; then
  cp "${BUNDLE_DIR}/compose.yml" "${APP_HOME}/compose.yml"
fi
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
