#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Vault container launcher — production hardened
# Binds to 127.0.0.1 only (not exposed to external network)
# Joins platform_microservice-network so backend services can resolve hostname
# ---------------------------------------------------------------------------

VAULT_CONTAINER_NAME="${VAULT_CONTAINER_NAME:-platform-stage-vault}"
VAULT_IMAGE="${VAULT_IMAGE:-hashicorp/vault:1.21.4}"
VAULT_DATA_DIR="${VAULT_DATA_DIR:-/home/halil/platform/state/vault/data}"
VAULT_CONFIG_DIR="${VAULT_CONFIG_DIR:-/home/halil/platform/repo/backend/devops/vault}"
VAULT_UNSEAL_KEY_DIR="${VAULT_UNSEAL_KEY_DIR:-/home/halil/platform/state/vault}"
BACKEND_NETWORK="${BACKEND_NETWORK:-platform_microservice-network}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[error] required command not found: $1" >&2
    exit 1
  fi
}

unseal_vault() {
  local addr="http://127.0.0.1:8200"
  local max_wait=30
  local elapsed=0

  echo "[vault] waiting for Vault API..."
  while ! curl -sf "${addr}/v1/sys/health" >/dev/null 2>&1 && [ $elapsed -lt $max_wait ]; do
    sleep 1
    elapsed=$((elapsed + 1))
  done

  if [ $elapsed -ge $max_wait ]; then
    echo "[vault] timeout waiting for Vault API" >&2
    return 1
  fi

  local sealed
  sealed=$(curl -s "${addr}/v1/sys/seal-status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('sealed','unknown'))")

  if [ "${sealed}" = "False" ]; then
    echo "[vault] already unsealed"
    return 0
  fi

  echo "[vault] unsealing with 3 keys..."
  for i in 1 2 3; do
    local key_file="${VAULT_UNSEAL_KEY_DIR}/vault-unseal-key-${i}"
    if [ ! -f "${key_file}" ]; then
      echo "[error] unseal key not found: ${key_file}" >&2
      return 1
    fi
    local key
    key=$(cat "${key_file}")
    curl -s -X POST "${addr}/v1/sys/unseal" -d "{\"key\": \"${key}\"}" >/dev/null
  done

  sealed=$(curl -s "${addr}/v1/sys/seal-status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('sealed','unknown'))")
  if [ "${sealed}" = "False" ]; then
    echo "[vault] unseal OK"
  else
    echo "[error] vault still sealed after unseal attempt" >&2
    return 1
  fi
}

main() {
  require_cmd docker
  require_cmd curl

  echo "[vault] pulling image ${VAULT_IMAGE}..."
  docker pull "${VAULT_IMAGE}" >/dev/null 2>&1 || echo "[vault] pull skipped (using cached image)"

  echo "[vault] stopping existing container..."
  docker rm -f "${VAULT_CONTAINER_NAME}" >/dev/null 2>&1 || true

  echo "[vault] starting container (127.0.0.1 binding)..."
  docker run -d \
    --name "${VAULT_CONTAINER_NAME}" \
    --restart unless-stopped \
    --cap-add IPC_LOCK \
    -p 127.0.0.1:8200:8200 \
    -p 127.0.0.1:8201:8201 \
    -v "${VAULT_DATA_DIR}:/vault/file" \
    -v "${VAULT_CONFIG_DIR}:/vault/config:ro" \
    "${VAULT_IMAGE}" vault server -config=/vault/config/vault.hcl >/dev/null

  # Join backend network so services can resolve 'platform-stage-vault' hostname
  echo "[vault] connecting to ${BACKEND_NETWORK}..."
  docker network connect "${BACKEND_NETWORK}" "${VAULT_CONTAINER_NAME}" 2>/dev/null \
    || echo "[vault] already connected to ${BACKEND_NETWORK}"

  # Auto-unseal if keys are present
  if [ -f "${VAULT_UNSEAL_KEY_DIR}/vault-unseal-key-1" ]; then
    unseal_vault
  else
    echo "[vault] no unseal keys found — manual unseal required"
  fi

  echo "[vault] container=${VAULT_CONTAINER_NAME} ports=127.0.0.1:8200,8201 network=${BACKEND_NETWORK}"
}

main "$@"
