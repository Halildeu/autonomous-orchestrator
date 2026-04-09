#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ENV="${DEPLOY_ENV:-stage}"
VAULT_ADDR="${VAULT_ADDR:?VAULT_ADDR required}"
VAULT_TOKEN="${VAULT_TOKEN:?VAULT_TOKEN required}"
VAULT_KV_MOUNT="${VAULT_KV_MOUNT:-secret}"
BACKEND_CONFIG_PATH_TEMPLATE="${BACKEND_CONFIG_PATH_TEMPLATE:-<env>/backend-deploy/config}"
OUTPUT_FILE="${OUTPUT_FILE:-/home/halil/platform/env/backend.env}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[error] required command not found: $1" >&2
    exit 1
  fi
}

resolve_path() {
  local raw="$1"
  local resolved

  resolved="${raw//<env>/${DEPLOY_ENV}}"
  resolved="${resolved#/}"
  printf '%s' "${resolved}"
}

kv_get_json() {
  local path="$1"
  local mount="$2"

  curl -sSf \
    -H "X-Vault-Token: ${VAULT_TOKEN}" \
    "${VAULT_ADDR%/}/v1/${mount}/data/${path}"
}

# Like kv_get_json but returns empty string instead of failing on 404.
# Used for optional Vault paths (db/*, jwt/*) that may not be seeded yet.
kv_get_json_optional() {
  local path="$1"
  local mount="$2"
  local http_code
  local body
  local tmp_file

  tmp_file="$(mktemp)"
  http_code="$(curl -sS -w '%{http_code}' -o "${tmp_file}" \
    -H "X-Vault-Token: ${VAULT_TOKEN}" \
    "${VAULT_ADDR%/}/v1/${mount}/data/${path}")" || true

  if [[ "${http_code}" == "200" ]]; then
    cat "${tmp_file}"
  elif [[ "${http_code}" == "404" ]]; then
    echo "[render] optional path ${mount}/${path} not found; using main config fallback" >&2
    printf ''
  else
    echo "[error] unexpected HTTP ${http_code} reading ${mount}/${path}" >&2
    rm -f "${tmp_file}"
    return 1
  fi
  rm -f "${tmp_file}"
}

kv_get_value() {
  local payload="$1"
  local key="$2"

  printf '%s' "${payload}" | json_get "${key}"
}

json_get() {
  local key="$1"
  python3 -c 'import json, sys; payload = json.load(sys.stdin); print(payload.get("data", {}).get("data", {}).get(sys.argv[1], ""), end="")' "$key"
}

derive_public_issuer() {
  local issuer="$1"
  local web_origin="$2"

  python3 - "$issuer" "$web_origin" <<'PY'
import sys
from urllib.parse import urlparse

issuer = (sys.argv[1] or "").strip().rstrip("/")
web_origin = (sys.argv[2] or "").strip().rstrip("/")

if not issuer or not web_origin:
    raise SystemExit(0)

marker = "/realms/"
if marker not in issuer:
    raise SystemExit(0)

realm = issuer.split(marker, 1)[1].strip("/")
if not realm:
    raise SystemExit(0)

parsed = urlparse(web_origin)
if not parsed.scheme or not parsed.netloc:
    raise SystemExit(0)

print(f"{parsed.scheme}://{parsed.netloc}/realms/{realm}", end="")
PY
}

write_kv() {
  local file="$1"
  local key="$2"
  local value="$3"

  if [[ "${value}" == *$'\n'* ]]; then
    echo "[error] ${key} contains a newline; backend.env only supports single-line values." >&2
    exit 1
  fi

  printf '%s=%s\n' "${key}" "${value}" >> "${file}"
}

main() {
  require_cmd curl
  require_cmd python3

  local mount
  local config_path
  local payload
  local auth_db_path
  local user_db_path
  local permission_db_path
  local variant_db_path
  local auth_jwt_path
  local auth_db_payload
  local user_db_payload
  local permission_db_payload
  local variant_db_payload
  local auth_jwt_payload
  local tmp_file
  local dir
  local missing=()
  local required_keys=(
    GIT_REMOTE_URL
    REPO_BRANCH
    GHCR_OWNER
    VAULT_URI
    VAULT_TOKEN
    KEYCLOAK_ISSUER_URI
    KEYCLOAK_JWKS_URI
    AUTH_VERIFICATION_BASE_URL
    AUTH_RESET_BASE_URL
    SERVICE_CLIENT_USER_SERVICE_SECRET
    PERMISSION_SERVICE_INTERNAL_API_KEY
    POSTGRES_USER
    POSTGRES_PASSWORD
    OPENFGA_STORE_ID
    OPENFGA_MODEL_ID
    CORE_DATA_DB_URL
    CORE_DATA_DB_USERNAME
    CORE_DATA_DB_PASSWORD
  )
  local ordered_keys=(
    GIT_REMOTE_URL
    REPO_BRANCH
    GHCR_OWNER
    GHCR_USERNAME
    GHCR_TOKEN
    IMAGE_TAG
    COMPOSE_PROJECT_NAME
    TZ
    COMPOSE_PROFILES
    API_GATEWAY_PORT
    VAULT_URI
    VAULT_SCHEME
    VAULT_TOKEN
    VAULT_FAIL_FAST
    KEYCLOAK_ISSUER_URI
    KEYCLOAK_JWKS_URI
    KEYCLOAK_PUBLIC_ISSUER_URI
    WEB_ORIGIN
    AUTH_VERIFICATION_BASE_URL
    AUTH_RESET_BASE_URL
    SERVICE_CLIENT_USER_SERVICE_SECRET
    PERMISSION_SERVICE_INTERNAL_API_KEY
    SECURITY_AUTH_ALLOWED_CLIENT_IDS
    POSTGRES_USER
    POSTGRES_PASSWORD
    POSTGRES_DB
    AUTH_DB_DDL_AUTO
    AUTH_DB_SCHEMA
    USER_DB_DDL_AUTO
    USER_DB_SCHEMA
    PERMISSION_DB_DDL_AUTO
    PERMISSION_DB_SCHEMA
    VARIANT_DB_DDL_AUTO
    VARIANT_DB_SCHEMA
    CORE_DATA_DB_SCHEMA
    OPENFGA_STORE_ID
    OPENFGA_MODEL_ID
    OPENFGA_LOG_LEVEL
    CORE_DATA_DB_URL
    CORE_DATA_DB_USERNAME
    CORE_DATA_DB_PASSWORD
    REPORT_MSSQL_HOST
    REPORT_MSSQL_PORT
    REPORT_MSSQL_DB
    REPORT_MSSQL_USERNAME
    REPORT_MSSQL_PASSWORD
    REPORT_PG_HOST
    REPORT_PG_PORT
    REPORT_PG_DB
    REPORT_PG_USERNAME
    REPORT_PG_PASSWORD
    SCHEMA_MSSQL_HOST
    SCHEMA_MSSQL_PORT
    SCHEMA_MSSQL_DB
    SCHEMA_MSSQL_USERNAME
    SCHEMA_MSSQL_PASSWORD
    SCHEMA_DEFAULT_SCHEMA
  )
  local key
  local value
  local keycloak_issuer_uri
  local keycloak_public_issuer_uri
  local web_origin

  mount="${VAULT_KV_MOUNT#/}"
  mount="${mount%/}"
  config_path="$(resolve_path "${BACKEND_CONFIG_PATH_TEMPLATE}")"
  auth_db_path="${DEPLOY_ENV}/db/auth-service"
  user_db_path="${DEPLOY_ENV}/db/user-service"
  permission_db_path="${DEPLOY_ENV}/db/permission-service"
  variant_db_path="${DEPLOY_ENV}/db/variant-service"
  auth_jwt_path="${DEPLOY_ENV}/jwt/auth-service"

  payload="$(kv_get_json_optional "${config_path}" "${mount}")"
  if [[ -z "${payload}" ]]; then
    echo "[render] WARNING: main config path ${mount}/${config_path} not found in Vault" >&2
    if [[ -f "${OUTPUT_FILE}" ]]; then
      echo "[render] keeping existing ${OUTPUT_FILE} (Vault path missing)" >&2
      return 0
    else
      echo "[error] main config path missing and no existing env file" >&2
      exit 1
    fi
  fi

  # Per-service DB/JWT paths are optional — if missing, per-service DB env vars
  # are skipped (the main config already contains shared POSTGRES_USER/PASSWORD).
  auth_db_payload="$(kv_get_json_optional "${auth_db_path}" "${mount}")"
  user_db_payload="$(kv_get_json_optional "${user_db_path}" "${mount}")"
  permission_db_payload="$(kv_get_json_optional "${permission_db_path}" "${mount}")"
  variant_db_payload="$(kv_get_json_optional "${variant_db_path}" "${mount}")"
  auth_jwt_payload="$(kv_get_json_optional "${auth_jwt_path}" "${mount}")"

  for key in "${required_keys[@]}"; do
    value="$(printf '%s' "${payload}" | json_get "${key}")"
    if [[ -z "${value}" ]]; then
      missing+=("${key}")
    fi
  done

  if [[ "${#missing[@]}" -gt 0 ]]; then
    echo "[render] WARNING: missing keys at ${mount}/${config_path}: ${missing[*]}" >&2
    if [[ -f "${OUTPUT_FILE}" ]]; then
      echo "[render] Vault config incomplete — keeping existing ${OUTPUT_FILE} (graceful degradation)" >&2
      return 0
    else
      echo "[error] Vault config incomplete and no existing env file to fall back to" >&2
      exit 1
    fi
  fi

  dir="$(dirname "${OUTPUT_FILE}")"
  mkdir -p "${dir}"
  chmod 700 "${dir}" 2>/dev/null || true

  tmp_file="$(mktemp "${dir}/backend.env.XXXXXX")"
  chmod 600 "${tmp_file}"
  printf '# rendered from Vault path: %s/%s\n' "${mount}" "${config_path}" > "${tmp_file}"
  printf '# generated_at=%s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${tmp_file}"

  for key in "${ordered_keys[@]}"; do
    value="$(printf '%s' "${payload}" | json_get "${key}")"
    if [[ -n "${value}" ]]; then
      write_kv "${tmp_file}" "${key}" "${value}"
    fi
  done

  keycloak_issuer_uri="$(printf '%s' "${payload}" | json_get "KEYCLOAK_ISSUER_URI")"
  keycloak_public_issuer_uri="$(printf '%s' "${payload}" | json_get "KEYCLOAK_PUBLIC_ISSUER_URI")"
  web_origin="$(printf '%s' "${payload}" | json_get "WEB_ORIGIN")"
  if [[ -z "${keycloak_public_issuer_uri}" ]]; then
    keycloak_public_issuer_uri="$(derive_public_issuer "${keycloak_issuer_uri}" "${web_origin}")"
    if [[ -n "${keycloak_public_issuer_uri}" ]]; then
      write_kv "${tmp_file}" "KEYCLOAK_PUBLIC_ISSUER_URI" "${keycloak_public_issuer_uri}"
    fi
  fi

  # Per-service DB credentials — only written when the dedicated Vault path exists.
  # When paths are missing, services use the shared POSTGRES_USER/PASSWORD from main config.
  write_kv_if_present() {
    local file="$1" key="$2" val="$3"
    [[ -n "${val}" ]] && write_kv "${file}" "${key}" "${val}"
  }

  if [[ -n "${auth_db_payload}" ]]; then
    write_kv_if_present "${tmp_file}" AUTH_SERVICE_DB_URL "$(kv_get_value "${auth_db_payload}" url)"
    write_kv_if_present "${tmp_file}" AUTH_SERVICE_DB_USERNAME "$(kv_get_value "${auth_db_payload}" user)"
    write_kv_if_present "${tmp_file}" AUTH_SERVICE_DB_PASSWORD "$(kv_get_value "${auth_db_payload}" password)"
  fi

  if [[ -n "${user_db_payload}" ]]; then
    write_kv_if_present "${tmp_file}" USER_SERVICE_DB_URL "$(kv_get_value "${user_db_payload}" url)"
    write_kv_if_present "${tmp_file}" USER_SERVICE_DB_USERNAME "$(kv_get_value "${user_db_payload}" user)"
    write_kv_if_present "${tmp_file}" USER_SERVICE_DB_PASSWORD "$(kv_get_value "${user_db_payload}" password)"
  fi

  if [[ -n "${permission_db_payload}" ]]; then
    write_kv_if_present "${tmp_file}" PERMISSION_SERVICE_DB_URL "$(kv_get_value "${permission_db_payload}" url)"
    write_kv_if_present "${tmp_file}" PERMISSION_SERVICE_DB_USERNAME "$(kv_get_value "${permission_db_payload}" user)"
    write_kv_if_present "${tmp_file}" PERMISSION_SERVICE_DB_PASSWORD "$(kv_get_value "${permission_db_payload}" password)"
  fi

  if [[ -n "${variant_db_payload}" ]]; then
    write_kv_if_present "${tmp_file}" VARIANT_SERVICE_DB_URL "$(kv_get_value "${variant_db_payload}" url)"
    write_kv_if_present "${tmp_file}" VARIANT_SERVICE_DB_USERNAME "$(kv_get_value "${variant_db_payload}" user)"
    write_kv_if_present "${tmp_file}" VARIANT_SERVICE_DB_PASSWORD "$(kv_get_value "${variant_db_payload}" password)"
  fi

  if [[ -n "${auth_jwt_payload}" ]]; then
    write_kv_if_present "${tmp_file}" AUTH_SERVICE_JWT_PRIVATE_KEY "$(kv_get_value "${auth_jwt_payload}" privateKey)"
    write_kv_if_present "${tmp_file}" AUTH_SERVICE_JWT_PUBLIC_KEY "$(kv_get_value "${auth_jwt_payload}" publicKey)"
  fi

  mv "${tmp_file}" "${OUTPUT_FILE}"
  chmod 600 "${OUTPUT_FILE}"

  echo "[render] wrote ${OUTPUT_FILE} from ${mount}/${config_path}"
}

main "$@"
