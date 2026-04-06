#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${STATE_DIR:-/home/halil/platform/state}"
PREVIOUS_RELEASE_FILE="${PREVIOUS_RELEASE_FILE:-${STATE_DIR}/web.previous-release}"
CURRENT_RELEASE_FILE="${CURRENT_RELEASE_FILE:-${STATE_DIR}/web.current-release}"
WEB_CURRENT_LINK="${WEB_CURRENT_LINK:-/home/halil/platform/web/current}"

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
echo "[rollback] frontend release=${previous_release}"
