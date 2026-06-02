#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/oracle-nl2sql}"
COMPOSE_FILE="${APP_HOME}/compose.yml"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${APP_HOME}/.env" ]]; then
  echo "Env file not found: ${APP_HOME}/.env" >&2
  exit 1
fi

cd "${APP_HOME}"
PODMAN_IGNORE_CGROUPSV1_WARNING=1 podman-compose -p oracle-nl2sql -f "${COMPOSE_FILE}" up -d
PODMAN_IGNORE_CGROUPSV1_WARNING=1 podman-compose -p oracle-nl2sql -f "${COMPOSE_FILE}" ps

