#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${STATE_DIR:-/home/halil/platform/state}"
PREVIOUS_RELEASE_FILE="${PREVIOUS_RELEASE_FILE:-${STATE_DIR}/web.previous-release}"
CURRENT_RELEASE_FILE="${CURRENT_RELEASE_FILE:-${STATE_DIR}/web.current-release}"
WEB_CURRENT_LINK="${WEB_CURRENT_LINK:-/home/halil/platform/web/current}"
NGINX_CONTAINER_ENABLED="${NGINX_CONTAINER_ENABLED:-false}"
NGINX_CONTAINER_SCRIPT="${NGINX_CONTAINER_SCRIPT:-$(cd "$(dirname "$0")" && pwd)/run-frontend-nginx-container.sh}"

if [[ ! -f "${PREVIOUS_RELEASE_FILE}" ]]; then
  echo "[error] previous frontend release not found: ${PREVIOUS_RELEASE_FILE}" >&2
  exit 1
fi

previous_release="$(tr -d '[:space:]' < "${PREVIOUS_RELEASE_FILE}")"
if [[ -z "${previous_release}" || ! -d "${previous_release}" ]]; then
  echo "[error] previous frontend release is invalid: ${previous_release:-empty}" >&2
  exit 1
fi

ln -sfn "${previous_release}" "${WEB_CURRENT_LINK}"
printf '%s\n' "${previous_release}" > "${CURRENT_RELEASE_FILE}"

if [[ "${NGINX_CONTAINER_ENABLED}" == "true" ]]; then
  if [[ ! -x "${NGINX_CONTAINER_SCRIPT}" ]]; then
    echo "[error] nginx container script missing or not executable: ${NGINX_CONTAINER_SCRIPT}" >&2
    exit 1
  fi
  "${NGINX_CONTAINER_SCRIPT}"
fi

echo "[rollback] frontend release=${previous_release}"
