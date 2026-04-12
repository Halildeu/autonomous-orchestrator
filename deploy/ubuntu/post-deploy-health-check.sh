#!/usr/bin/env bash
set -euo pipefail
# Post-deploy health validation — runs after deploy-backend.sh
# Ensures ALL services are healthy, Vault unsealed, endpoints reachable.
# Updated: Vault auto-unseal retry loop (vault-unseal watcher needs time)

echo "[health-check] Starting post-deploy validation..."
echo "[health-check] Waiting 30s for services to stabilize..."
sleep 30

FAILURES=0

# ---- 1. Vault sealed check (retry loop — vault-unseal watcher may need time) ----
VAULT_RETRIES=12
VAULT_SEALED="True"
echo "[health-check] Checking Vault seal status (max ${VAULT_RETRIES} retries, 10s interval)..."
for i in $(seq 1 $VAULT_RETRIES); do
  VAULT_SEALED=$(docker exec platform-vault-1 vault status -format=json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('sealed','unknown'))" 2>/dev/null || echo "unknown")
  if [[ "$VAULT_SEALED" == "False" ]]; then
    echo "  OK: vault unsealed (attempt $i)"
    break
  fi
  if [[ $i -lt $VAULT_RETRIES ]]; then
    echo "  WAIT: vault sealed=$VAULT_SEALED (attempt $i/$VAULT_RETRIES, retrying in 10s...)"
    sleep 10
  else
    echo "  FAIL: vault still sealed after $VAULT_RETRIES attempts"
    FAILURES=$((FAILURES + 1))
  fi
done

# ---- 2. If Vault was sealed, wait extra 20s for dependent services to recover ----
if [[ "$VAULT_SEALED" == "False" ]]; then
  # Check if auth-dependent services need restart
  for svc in auth-service user-service variant-service; do
    container="platform-${svc}-1"
    status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container" 2>/dev/null || echo "missing")
    if [[ "$status" != "healthy" ]]; then
      echo "[health-check] Restarting $svc (unhealthy after Vault unseal)..."
      docker restart "$container" 2>/dev/null || true
    fi
  done
  echo "[health-check] Waiting 30s for Vault-dependent services to recover..."
  sleep 30
fi

# ---- 3. Docker health status ----
for svc in postgres-db vault keycloak openfga discovery-server permission-service auth-service user-service variant-service core-data-service report-service api-gateway web-nginx; do
  container="platform-${svc}-1"
  status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container" 2>/dev/null || echo "missing")
  if [[ "$status" == "healthy" || "$status" == "no-healthcheck" ]]; then
    echo "  OK: $svc ($status)"
  else
    echo "  FAIL: $svc ($status)"
    FAILURES=$((FAILURES + 1))
  fi
done

# ---- 4. OpenFGA health ----
OPENFGA=$(curl -sf http://localhost:4000/healthz 2>/dev/null || echo '{"status":"FAIL"}')
if echo "$OPENFGA" | grep -q "SERVING"; then
  echo "  OK: openfga SERVING"
else
  echo "  FAIL: openfga $OPENFGA"
  FAILURES=$((FAILURES + 1))
fi

echo ""
if [[ $FAILURES -gt 0 ]]; then
  echo "[health-check] FAIL: $FAILURES service(s) unhealthy"
  exit 1
fi
echo "[health-check] PASS: all services healthy"
