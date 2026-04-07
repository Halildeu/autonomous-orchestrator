#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_DIR="${REPO_DIR:-/home/halil/platform/repo}"
ENV_FILE="${ENV_FILE:-/home/halil/platform/env/backend.env}"
STATE_DIR="${STATE_DIR:-/home/halil/platform/state}"
PREVIOUS_TAG_FILE="${PREVIOUS_TAG_FILE:-${STATE_DIR}/backend.previous-image-tag}"
CURRENT_TAG_FILE="${CURRENT_TAG_FILE:-${STATE_DIR}/backend.current-image-tag}"

if [[ ! -f "${PREVIOUS_TAG_FILE}" ]]; then
  echo "[error] previous image tag not found: ${PREVIOUS_TAG_FILE}" >&2
  exit 1
fi

previous_tag="$(tr -d '[:space:]' < "${PREVIOUS_TAG_FILE}")"
current_tag=""
if [[ -f "${CURRENT_TAG_FILE}" ]]; then
  current_tag="$(tr -d '[:space:]' < "${CURRENT_TAG_FILE}")"
fi

if [[ -z "${previous_tag}" ]]; then
  echo "[error] previous image tag is empty." >&2
  exit 1
fi

if [[ -n "${current_tag}" && "${previous_tag}" = "${current_tag}" ]]; then
  echo "[error] previous image tag matches current tag (${current_tag}); refusing noop rollback." >&2
  exit 1
fi

ENV_FILE="${ENV_FILE}" \
REPO_DIR="${REPO_DIR}" \
STATE_DIR="${STATE_DIR}" \
TARGET_IMAGE_TAG="${previous_tag}" \
"${SCRIPT_DIR}/deploy-backend.sh"
