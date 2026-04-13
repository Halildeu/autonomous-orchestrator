#!/bin/bash
# Platform cold-start script — starts all services in correct order.
# Usage: /home/halil/platform/scripts/platform-start.sh

REPO_DIR="/home/halil/platform/repo/backend"
ENV_FILE="/home/halil/platform/env/backend.env"
COMPOSE="docker compose -f ${REPO_DIR}/../deploy/docker-compose.prod.yml --env-file ${ENV_FILE} --profile extras"
UNSEAL_SCRIPT="/home/halil/platform/scripts/vault-auto-unseal.sh"

export DOCKER_PULL_POLICY=never

echo "========================================="
echo "  PLATFORM START"
echo "========================================="

# Phase 1: Infrastructure (no vault dependency)
echo "[phase-1] Infrastructure..."
$COMPOSE up -d postgres-db vault keycloak openfga-migrate openfga discovery-server loki tempo prometheus 2>&1 | tail -3
sleep 5

# Phase 1b: Vault unseal
echo "[phase-1b] Vault unseal..."
bash "$UNSEAL_SCRIPT" || true

# Wait for vault healthy (max 30s)
for i in $(seq 1 15); do
  docker exec platform-vault-1 vault status >/dev/null 2>&1 && break
  sleep 2
done

# Phase 2: Backend services (need vault + discovery)
echo "[phase-2] Backend services..."
$COMPOSE up -d permission-service 2>&1 | tail -2
sleep 20
$COMPOSE up -d auth-service user-service variant-service core-data-service report-service schema-service 2>&1 | tail -2
sleep 15
$COMPOSE up -d api-gateway 2>&1 | tail -2

# Phase 3: Supporting
echo "[phase-3] Supporting..."
$COMPOSE up -d web-nginx service-manager grafana promtail vault-unseal vault-snapshot vault-audit-init 2>&1 | tail -2
docker rm -f platform-web-nginx 2>/dev/null || true

echo ""
HEALTHY=$(docker ps --filter "name=platform-" --filter "health=healthy" -q | wc -l)
TOTAL=$(docker ps --filter "name=platform-" -q | wc -l)
echo "========================================="
echo "  Running: $TOTAL, Healthy: $HEALTHY"
echo "========================================="
