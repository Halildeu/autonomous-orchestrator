#!/bin/bash
# Vault auto-unseal — runs after vault container starts.
# Used by: platform-start.sh, cron @reboot, deploy script.

VAULT_CONTAINER="platform-vault-1"
KEYS_DIR="/home/halil/platform/state/vault"

echo "[$(date)] vault-auto-unseal: starting..."

# Wait for vault container (max 60s)
for i in $(seq 1 20); do
  docker exec "$VAULT_CONTAINER" vault status >/dev/null 2>&1
  rc=$?
  [ "$rc" -eq 0 ] && { echo "[$(date)] vault-auto-unseal: already unsealed"; exit 0; }
  [ "$rc" -eq 2 ] && break  # sealed but running
  sleep 3
done

# Unseal
echo "[$(date)] vault-auto-unseal: unsealing..."
for key_file in "${KEYS_DIR}"/vault-unseal-key-*; do
  [ -f "$key_file" ] || continue
  docker exec "$VAULT_CONTAINER" vault operator unseal "$(cat "$key_file" | tr -d '[:space:]')" >/dev/null 2>&1 || true
done

docker exec "$VAULT_CONTAINER" vault status >/dev/null 2>&1
rc=$?
[ "$rc" -eq 0 ] && echo "[$(date)] vault-auto-unseal: SUCCESS" || echo "[$(date)] vault-auto-unseal: FAILED (rc=$rc)"
exit 0  # always exit 0 to not break caller
