#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
DEPLOY_ENV="${DEPLOY_ENV:-stage}"
VAULT_ADDR="${VAULT_ADDR:?VAULT_ADDR required}"
VAULT_APPROLE_MOUNT="${VAULT_APPROLE_MOUNT:-auth/approle}"
VAULT_APPROLE_ROLE_NAME="${VAULT_APPROLE_ROLE_NAME:-backend-deploy-${DEPLOY_ENV}}"
VAULT_APPROLE_ROLE_ID_FILE="${VAULT_APPROLE_ROLE_ID_FILE:-/home/halil/platform/state/vault/approle/${VAULT_APPROLE_ROLE_NAME}.role-id}"
VAULT_APPROLE_SECRET_ID_FILE="${VAULT_APPROLE_SECRET_ID_FILE:-/home/halil/platform/state/vault/approle/${VAULT_APPROLE_ROLE_NAME}.secret-id}"
VAULT_TOKEN_REVOKE_ON_EXIT="${VAULT_TOKEN_REVOKE_ON_EXIT:-true}"
APPROLE_CLIENT_TOKEN=""
APPROLE_REVOKE_FLAG=""

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[error] required command not found: $1" >&2
    exit 1
  fi
}

read_trimmed_file() {
  local path="$1"

  if [[ ! -f "${path}" ]]; then
    echo "[error] file not found: ${path}" >&2
    exit 1
  fi

  python3 - "$path" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).read_text(encoding="utf-8").strip(), end="")
PY
}

json_get() {
  local key="$1"

  python3 -c 'import json, sys; payload = json.load(sys.stdin); print(payload.get("auth", {}).get(sys.argv[1], "") or "", end="")' "${key}"
}

revoke_token() {
  if [[ "${APPROLE_REVOKE_FLAG}" != "true" && "${APPROLE_REVOKE_FLAG}" != "1" && "${APPROLE_REVOKE_FLAG}" != "yes" ]]; then
    return 0
  fi

  if [[ -z "${APPROLE_CLIENT_TOKEN}" ]]; then
    return 0
  fi

  curl -sS -o /dev/null \
    -H "X-Vault-Token: ${APPROLE_CLIENT_TOKEN}" \
    -X POST "${VAULT_ADDR%/}/v1/auth/token/revoke-self" || true
}

main() {
  require_cmd curl
  require_cmd python3

  local role_id
  local secret_id
  local mount
  local login_url
  local payload
  local login_response

  role_id="$(read_trimmed_file "${VAULT_APPROLE_ROLE_ID_FILE}")"
  secret_id="$(read_trimmed_file "${VAULT_APPROLE_SECRET_ID_FILE}")"
  mount="${VAULT_APPROLE_MOUNT#/}"
  mount="${mount%/}"
  login_url="${VAULT_ADDR%/}/v1/${mount}/login"

  payload="$(python3 - <<'PY' "$role_id" "$secret_id"
import json
import sys

print(json.dumps({"role_id": sys.argv[1], "secret_id": sys.argv[2]}))
PY
)"

  login_response="$(curl -sSf \
    -H 'Content-Type: application/json' \
    -X POST "${login_url}" \
    -d "${payload}")"

  APPROLE_CLIENT_TOKEN="$(printf '%s' "${login_response}" | json_get client_token)"
  if [[ -z "${APPROLE_CLIENT_TOKEN}" ]]; then
    echo "[error] approle login returned empty client_token." >&2
    exit 1
  fi

  APPROLE_REVOKE_FLAG="$(printf '%s' "${VAULT_TOKEN_REVOKE_ON_EXIT}" | tr '[:upper:]' '[:lower:]')"
  trap revoke_token EXIT

  DEPLOY_ENV="${DEPLOY_ENV}" \
  VAULT_ADDR="${VAULT_ADDR}" \
  VAULT_TOKEN="${APPROLE_CLIENT_TOKEN}" \
  OUTPUT_FILE="${OUTPUT_FILE:-/home/halil/platform/env/backend.env}" \
  "${SCRIPT_DIR}/render-backend-env.sh"
}

main "$@"
