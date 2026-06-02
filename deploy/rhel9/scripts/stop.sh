#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
COMPOSE_FILE="${APP_HOME}/compose.yml"

cd "${APP_HOME}"
PODMAN_IGNORE_CGROUPSV1_WARNING=1 podman-compose -p oracle-nl2sql -f "${COMPOSE_FILE}" down

