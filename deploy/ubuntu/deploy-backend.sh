#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_DIR="${REPO_DIR:-/home/halil/platform/repo}"
BACKEND_DIR="${BACKEND_DIR:-${REPO_DIR}/backend}"
ENV_FILE="${ENV_FILE:-/home/halil/platform/env/backend.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${BACKEND_DIR}/docker-compose.prod.yml}"
REPO_BRANCH="${REPO_BRANCH:-main}"
PINNED_REPO_BRANCH="${REPO_BRANCH}"
GIT_REMOTE_URL="${GIT_REMOTE_URL:-}"
COMPOSE_PROFILES="${COMPOSE_PROFILES:-}"
STATE_DIR="${STATE_DIR:-/home/halil/platform/state}"
CURRENT_TAG_FILE="${CURRENT_TAG_FILE:-${STATE_DIR}/backend.current-image-tag}"
PREVIOUS_TAG_FILE="${PREVIOUS_TAG_FILE:-${STATE_DIR}/backend.previous-image-tag}"
TARGET_IMAGE_TAG="${TARGET_IMAGE_TAG:-}"
BUILD_LOCAL="${BUILD_LOCAL:-false}"
BUILD_COMPOSE_FILE="${BUILD_COMPOSE_FILE:-${BACKEND_DIR}/docker-compose.yml}"
DOCKER_PULL_POLICY="${DOCKER_PULL_POLICY:-always}"
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

print_compose_diagnostics() {
  local compose_flags="$1"
  local services=(
    discovery-server
    postgres-db
    openfga-migrate
    openfga
    permission-service
    auth-service
    user-service
    variant-service
    core-data-service
    api-gateway
  )

  echo "[diag] docker compose ps --all" >&2
  # shellcheck disable=SC2086
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ${compose_flags} ps --all || true

  for service in "${services[@]}"; do
    echo "[diag] docker compose logs --tail=200 ${service}" >&2
    # shellcheck disable=SC2086
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ${compose_flags} logs --no-color --tail=200 "${service}" || true
  done
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

bootstrap_vault_credentials_from_env_file() {
  local file_vault_token=""
  local file_vault_addr=""

  if [[ ! -f "${ENV_FILE}" ]]; then
    return 0
  fi

  if [[ -z "${VAULT_TOKEN:-}" ]]; then
    file_vault_token="$(read_env_value VAULT_TOKEN)"
    if [[ -n "${file_vault_token}" ]]; then
      VAULT_TOKEN="${file_vault_token}"
      export VAULT_TOKEN
      echo "[deploy] bootstrapped VAULT_TOKEN from existing env file."
    fi
  fi

  if [[ -z "${VAULT_ADDR:-}" ]]; then
    file_vault_addr="$(read_env_value VAULT_URI)"
    if [[ -n "${file_vault_addr}" ]]; then
      VAULT_ADDR="${file_vault_addr}"
      export VAULT_ADDR
      echo "[deploy] bootstrapped VAULT_ADDR from existing env file."
    fi
  fi
}

sync_repo() {
  if [[ -d "${REPO_DIR}/.git" ]]; then
    git -C "${REPO_DIR}" fetch origin "${REPO_BRANCH}"
    if git -C "${REPO_DIR}" show-ref --verify --quiet "refs/heads/${REPO_BRANCH}"; then
      git -C "${REPO_DIR}" checkout "${REPO_BRANCH}"
      git -C "${REPO_DIR}" merge --ff-only FETCH_HEAD
    else
      git -C "${REPO_DIR}" checkout -b "${REPO_BRANCH}" FETCH_HEAD
    fi
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

compose_run() {
  # Make the active image tag authoritative for compose interpolation.
  IMAGE_TAG="${IMAGE_TAG}" docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

container_name_for() {
  printf 'platform-%s-1' "$1"
}

wait_for_service_state() {
  local service="$1"
  local expected="$2"
  local timeout_seconds="${3:-90}"
  local container_name
  local deadline
  local state=""

  container_name="$(container_name_for "${service}")"
  deadline=$((SECONDS + timeout_seconds))

  while (( SECONDS < deadline )); do
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_name}" 2>/dev/null || true)"

    if [[ "${state}" == "${expected}" ]]; then
      echo "[wait] ${service} -> ${state}"
      return 0
    fi

    case "${state}" in
      unhealthy|exited|dead)
        echo "[error] ${service} reached terminal state: ${state}" >&2
        docker logs --tail 200 "${container_name}" || true
        return 1
        ;;
      "")
        echo "[wait] ${service} -> missing"
        ;;
      *)
        echo "[wait] ${service} -> ${state}"
        ;;
    esac

    sleep 2
  done

  echo "[error] timeout waiting for ${service} to become ${expected}; last_state=${state}" >&2
  docker logs --tail 200 "${container_name}" || true
  return 1
}

main() {
  require_cmd git
  require_cmd docker

  pre_sync_existing_repo
  bootstrap_vault_credentials_from_env_file
  maybe_render_env
  load_env_file

  # --- Vault URI validation and correction ---
  # Canonical internal Vault address: http://vault:8200
  # Reject stale hostnames (platform-stage-vault, platform-vault, etc.)
  validate_and_fix_vault_uri() {
    local canonical_vault_uri="http://vault:8200"
    local current_uri
    current_uri="$(read_env_value VAULT_URI)"

    # Fix HTTPS → HTTP (internal Docker network uses HTTP, TLS at edge)
    if [[ "${current_uri}" == https://vault:* ]]; then
      current_uri="${current_uri/https:\/\//http:\/\/}"
      echo "[deploy] fixed VAULT_URI scheme: https→http"
    fi

    # Reject stale/wrong hostnames — only "vault" is valid in compose network
    if [[ -n "${current_uri}" && "${current_uri}" != http://vault:* && "${current_uri}" != https://vault:* && "${current_uri}" != http://127.0.0.1:* && "${current_uri}" != https://127.0.0.1:* ]]; then
      echo "[deploy] WARNING: stale VAULT_URI detected: ${current_uri}" >&2
      echo "[deploy] overriding with canonical: ${canonical_vault_uri}" >&2
      current_uri="${canonical_vault_uri}"
    fi

    # Set canonical if empty
    if [[ -z "${current_uri}" ]]; then
      current_uri="${canonical_vault_uri}"
    fi

    # Persist corrections
    upsert_env_value VAULT_URI "${current_uri}"
    upsert_env_value VAULT_SCHEME "http"
    export VAULT_URI="${current_uri}"
    export VAULT_SCHEME="http"
    echo "[deploy] VAULT_URI=${current_uri}"
  }
  validate_and_fix_vault_uri

  REPO_BRANCH="${PINNED_REPO_BRANCH}"
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
    if [[ "${rc}" -ne 0 && -n "${compose_flags:-}" ]]; then
      print_compose_diagnostics "${compose_flags}" || true
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

  export IMAGE_TAG="${active_image_tag}"
  echo "[deploy] branch=${REPO_BRANCH} image_tag=${IMAGE_TAG}"

  compose_flags="$(compose_cmd)"

  # shellcheck disable=SC2206
  local compose_args=( ${compose_flags} )

  compose_run "${compose_args[@]}" config --services >/dev/null

  # --- STRATEGY ---
  # Backend deploy ONLY recreates application services.
  # Infrastructure (postgres, vault, keycloak, nginx, observability) stays RUNNING.
  # This prevents: Vault timeout, Keycloak cold-start, data loss.
  #
  # If infra config changed, run: docker compose up -d --force-recreate <service>

  local backend_services=(
    discovery-server
    permission-service
    auth-service
    user-service
    variant-service
    core-data-service
    report-service
    api-gateway
  )

  local build_flag
  build_flag="$(printf '%s' "${BUILD_LOCAL}" | tr '[:upper:]' '[:lower:]')"

  if [[ "${build_flag}" == "true" || "${build_flag}" == "1" ]]; then
    # ── Local build mode ──
    # Build images on this host, tag them to match GHCR names.
    # Eliminates GHCR pull (~25min on slow connections).
    echo "[deploy] LOCAL BUILD mode — building images on host"

    local ghcr_owner
    ghcr_owner="$(printf '%s' "${GHCR_OWNER:-halildeu}" | tr '[:upper:]' '[:lower:]')"

    docker compose -f "${BUILD_COMPOSE_FILE}" build 2>&1 | tail -5

    local img svc target tagged=0
    for img in $(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '^serban-'); do
      svc="${img%%:*}"
      svc="${svc#serban-}"
      target="ghcr.io/${ghcr_owner}/platform-ssot-${svc}:${IMAGE_TAG}"
      docker tag "${img}" "${target}"
      tagged=$((tagged + 1))
    done
    echo "[deploy] tagged ${tagged} images as ${IMAGE_TAG}"

    # Also tag as main-stable for rollback support
    for img in $(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '^serban-'); do
      svc="${img%%:*}"
      svc="${svc#serban-}"
      docker tag "${img}" "ghcr.io/${ghcr_owner}/platform-ssot-${svc}:main-stable"
    done

    export DOCKER_PULL_POLICY="never"

    # Clean old images to prevent disk fill
    docker image prune -f --filter "until=24h" >/dev/null 2>&1 || true
  else
    # ── Remote pull mode (default) ──
    echo "[deploy] REMOTE PULL mode — pulling images from GHCR"
    compose_run "${compose_args[@]}" pull "${backend_services[@]}" || true
  fi

  # Ensure infrastructure is up.
  # Force-recreate vault sidecars to pick up any script changes from this deploy.
  compose_run "${compose_args[@]}" up -d postgres-db openfga-migrate openfga vault keycloak
  compose_run "${compose_args[@]}" up -d --force-recreate vault-unseal vault-audit-init vault-snapshot 2>/dev/null || true
  wait_for_service_state postgres-db healthy 60
  wait_for_service_state vault healthy 120
  wait_for_service_state openfga running 60

  # Vault preflight — verify unsealed and accessible from deploy host
  vault_preflight() {
    local vault_container
    vault_container="$(container_name_for vault)"
    local status_json
    status_json="$(docker exec "${vault_container}" vault status -format=json 2>/dev/null || true)"
    if [[ -n "${status_json}" ]]; then
      local sealed
      sealed="$(printf '%s' "${status_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sealed","unknown"))' 2>/dev/null || echo "unknown")"
      echo "[deploy] vault preflight: sealed=${sealed}"
      if [[ "${sealed}" == "true" ]]; then
        echo "[error] Vault is still sealed after health wait. Unseal keys may be missing." >&2
        echo "[deploy] vault-unseal logs:" >&2
        docker logs --tail 20 "$(container_name_for vault-unseal)" 2>&1 || true
        return 1
      fi
    else
      echo "[error] cannot reach Vault inside container" >&2
      return 1
    fi
  }
  vault_preflight

  # Recreate backend services with new images (--force-recreate only touches these)
  compose_run "${compose_args[@]}" up -d --force-recreate --no-deps discovery-server
  wait_for_service_state discovery-server healthy 90

  compose_run "${compose_args[@]}" up -d --force-recreate --no-deps permission-service
  wait_for_service_state permission-service healthy 120

  compose_run "${compose_args[@]}" up -d --force-recreate --no-deps auth-service user-service variant-service core-data-service report-service
  wait_for_service_state auth-service healthy 120
  wait_for_service_state user-service healthy 120
  wait_for_service_state variant-service healthy 120
  wait_for_service_state core-data-service healthy 120
  wait_for_service_state report-service healthy 120

  compose_run "${compose_args[@]}" up -d --force-recreate --no-deps api-gateway
  wait_for_service_state api-gateway healthy 90

  # Ensure supporting services are up (idempotent).
  # Nginx config is generated from template via envsubst at container start —
  # Docker service names (keycloak, api-gateway) are ALWAYS correct.
  compose_run "${compose_args[@]}" up -d web-nginx service-manager vault-audit-init vault-snapshot loki promtail tempo prometheus grafana 2>/dev/null || true

  # Kill any standalone nginx container from old frontend deploys
  docker rm -f platform-web-nginx 2>/dev/null || true

  # Remove orphan containers (old names, deleted services)
  compose_run "${compose_args[@]}" up -d --remove-orphans 2>/dev/null || true

  compose_run "${compose_args[@]}" ps

  printf '%s\n' "${active_image_tag}" > "${CURRENT_TAG_FILE}"
  trap - EXIT

  git -C "${REPO_DIR}" rev-parse --short HEAD
}

main "$@"
