#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_DIR="${REPO_DIR:-/home/halil/platform/repo}"
BACKEND_DIR="${BACKEND_DIR:-${REPO_DIR}/backend}"
ENV_FILE="${ENV_FILE:-/home/halil/platform/env/backend.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${BACKEND_DIR}/docker-compose.prod.yml}"
REPO_BRANCH="${REPO_BRANCH:-main}"
GIT_REMOTE_URL="${GIT_REMOTE_URL:-}"
COMPOSE_PROFILES="${COMPOSE_PROFILES:-}"
STATE_DIR="${STATE_DIR:-/home/halil/platform/state}"
CURRENT_TAG_FILE="${CURRENT_TAG_FILE:-${STATE_DIR}/backend.current-image-tag}"
PREVIOUS_TAG_FILE="${PREVIOUS_TAG_FILE:-${STATE_DIR}/backend.previous-image-tag}"
TARGET_IMAGE_TAG="${TARGET_IMAGE_TAG:-}"
RENDER_ENV_BEFORE_DEPLOY="${RENDER_ENV_BEFORE_DEPLOY:-false}"
DEPLOY_ENV="${DEPLOY_ENV:-stage}"
VAULT_ADDR="${VAULT_ADDR:-}"
VAULT_APPROLE_ROLE_NAME="${VAULT_APPROLE_ROLE_NAME:-}"
VAULT_APPROLE_ROLE_ID_FILE="${VAULT_APPROLE_ROLE_ID_FILE:-}"
VAULT_APPROLE_SECRET_ID_FILE="${VAULT_APPROLE_SECRET_ID_FILE:-}"
VAULT_TOKEN_REVOKE_ON_EXIT="${VAULT_TOKEN_REVOKE_ON_EXIT:-true}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[error] required command not found: $1" >&2
    exit 1
  fi
}

load_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "[error] env file not found: ${ENV_FILE}" >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
}

read_env_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1)}' "${ENV_FILE}" | tail -n 1
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file

  tmp_file="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    $0 ~ ("^" key "=") {
      if (!updated) {
        print key "=" value
        updated = 1
      }
      next
    }
    { print }
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "${ENV_FILE}" > "${tmp_file}"
  mv "${tmp_file}" "${ENV_FILE}"
}

maybe_render_env() {
  local render_flag
  render_flag="$(printf '%s' "${RENDER_ENV_BEFORE_DEPLOY}" | tr '[:upper:]' '[:lower:]')"
  case "${render_flag}" in
    true|1|yes)
      ;;
    *)
      return 0
      ;;
  esac

  if [[ -z "${VAULT_ADDR}" ]]; then
    echo "[error] VAULT_ADDR required when RENDER_ENV_BEFORE_DEPLOY=true." >&2
    exit 1
  fi

  if [[ -n "${VAULT_TOKEN:-}" ]]; then
    DEPLOY_ENV="${DEPLOY_ENV}" \
    VAULT_ADDR="${VAULT_ADDR}" \
    VAULT_TOKEN="${VAULT_TOKEN}" \
    OUTPUT_FILE="${ENV_FILE}" \
    "${SCRIPT_DIR}/render-backend-env.sh"
    return 0
  fi

  DEPLOY_ENV="${DEPLOY_ENV}" \
  VAULT_ADDR="${VAULT_ADDR}" \
  OUTPUT_FILE="${ENV_FILE}" \
  VAULT_APPROLE_ROLE_NAME="${VAULT_APPROLE_ROLE_NAME}" \
  VAULT_APPROLE_ROLE_ID_FILE="${VAULT_APPROLE_ROLE_ID_FILE}" \
  VAULT_APPROLE_SECRET_ID_FILE="${VAULT_APPROLE_SECRET_ID_FILE}" \
  VAULT_TOKEN_REVOKE_ON_EXIT="${VAULT_TOKEN_REVOKE_ON_EXIT}" \
  "${SCRIPT_DIR}/render-backend-env-approle.sh"
}

sync_repo() {
  if [[ -d "${REPO_DIR}/.git" ]]; then
    git -C "${REPO_DIR}" fetch origin "${REPO_BRANCH}"
    git -C "${REPO_DIR}" checkout "${REPO_BRANCH}"
    git -C "${REPO_DIR}" pull --ff-only origin "${REPO_BRANCH}"
    return 0
  fi

  if [[ -z "${GIT_REMOTE_URL}" ]]; then
    echo "[error] repo missing at ${REPO_DIR} and GIT_REMOTE_URL is empty." >&2
    exit 1
  fi

  mkdir -p "$(dirname "${REPO_DIR}")"
  git clone --branch "${REPO_BRANCH}" --depth 1 "${GIT_REMOTE_URL}" "${REPO_DIR}"
}

pre_sync_existing_repo() {
  if [[ -d "${REPO_DIR}/.git" ]]; then
    sync_repo
  fi
}

compose_cmd() {
  local args=()
  local profile

  if [[ -n "${COMPOSE_PROFILES}" ]]; then
    IFS=',' read -r -a args <<< "${COMPOSE_PROFILES}"
    for profile in "${args[@]}"; do
      profile="$(echo "${profile}" | xargs)"
      [[ -n "${profile}" ]] || continue
      printf -- "--profile %s " "${profile}"
    done
  fi
}

main() {
  require_cmd git
  require_cmd docker

  pre_sync_existing_repo
  maybe_render_env
  load_env_file
  sync_repo
  mkdir -p "${STATE_DIR}"

  if [[ -n "${GHCR_USERNAME:-}" && -n "${GHCR_TOKEN:-}" ]]; then
    echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin >/dev/null
  fi

  local compose_flags
  local original_image_tag
  local active_image_tag
  local image_tag_updated="0"

  original_image_tag="$(read_env_value IMAGE_TAG)"
  active_image_tag="${original_image_tag:-${IMAGE_TAG:-main-stable}}"

  restore_image_tag_on_error() {
    local rc=$?
    if [[ "${rc}" -ne 0 && "${image_tag_updated}" = "1" && -n "${original_image_tag}" ]]; then
      upsert_env_value IMAGE_TAG "${original_image_tag}"
    fi
    exit "${rc}"
  }

  trap restore_image_tag_on_error EXIT

  if [[ -n "${TARGET_IMAGE_TAG}" && "${TARGET_IMAGE_TAG}" != "${active_image_tag}" ]]; then
    if [[ -n "${active_image_tag}" ]]; then
      printf '%s\n' "${active_image_tag}" > "${PREVIOUS_TAG_FILE}"
    fi
    upsert_env_value IMAGE_TAG "${TARGET_IMAGE_TAG}"
    IMAGE_TAG="${TARGET_IMAGE_TAG}"
    active_image_tag="${TARGET_IMAGE_TAG}"
    image_tag_updated="1"
  fi

  compose_flags="$(compose_cmd)"

  # shellcheck disable=SC2086
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ${compose_flags} config --services >/dev/null
  # shellcheck disable=SC2086
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ${compose_flags} pull
  # shellcheck disable=SC2086
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ${compose_flags} up -d
  # shellcheck disable=SC2086
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ${compose_flags} ps

  printf '%s\n' "${active_image_tag}" > "${CURRENT_TAG_FILE}"
  trap - EXIT

  git -C "${REPO_DIR}" rev-parse --short HEAD
}

main "$@"
