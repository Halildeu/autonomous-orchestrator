#!/usr/bin/env bash
set -euo pipefail
# Post-deploy health validation — runs after deploy-backend.sh
# Ensures ALL services are healthy, Vault unsealed, endpoints reachable.

echo "[health-check] Starting post-deploy validation..."

FAILURES=0

# 1. Docker health status
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

# 2. Vault sealed check
SEALED=$(docker exec platform-vault-1 vault status -format=json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('sealed','unknown'))" 2>/dev/null || echo "unknown")
if [[ "$SEALED" == "False" ]]; then
  echo "  OK: vault unsealed"
else
  echo "  FAIL: vault sealed=$SEALED"
  FAILURES=$((FAILURES + 1))
fi

# 3. OpenFGA health
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
