#!/usr/bin/env bash
# docker-smoke-test.sh — Docker compose smoke test for dev platform
# Starts all services, waits for health, tests Zanzibar endpoints, reports JSON.
# Exit: 0 = all PASS, 1 = any FAIL
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/backend/docker-compose.yml"
REPORT_DIR="$REPO_ROOT/.cache/reports/docker-smoke"
REPORT_FILE="$REPORT_DIR/smoke-result.v1.json"

TIMEOUT=60
SKIP_CLEANUP=false

# ── Parse flags ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout)      TIMEOUT="$2"; shift 2 ;;
    --skip-cleanup) SKIP_CLEANUP=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--timeout SECS] [--skip-cleanup]"
      echo "  --timeout       Health check timeout per service (default: 60)"
      echo "  --skip-cleanup  Keep containers running after test"
      exit 0 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
RESULTS="[]"
START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

add_result() {
  local name="$1" status="$2" detail="$3"
  RESULTS=$(printf '%s' "$RESULTS" | python3 -c "
import sys, json
r = json.load(sys.stdin)
r.append({'name': '$name', 'status': '$status', 'detail': '''$detail'''})
print(json.dumps(r))
")
  if [[ "$status" == "PASS" ]]; then ((PASS_COUNT++)); else ((FAIL_COUNT++)); fi
  if [[ "$status" == "PASS" ]]; then
    echo "  [PASS] $name"
  else
    echo "  [FAIL] $name — $detail"
  fi
}

cleanup() {
  if [[ "$SKIP_CLEANUP" == "true" ]]; then
    echo ">> --skip-cleanup: containers left running"
    return
  fi
  echo ">> Cleaning up containers..."
  docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans --timeout 15 2>/dev/null || true
}

wait_for_health() {
  local svc="$1" url="$2" elapsed=0
  while [[ $elapsed -lt $TIMEOUT ]]; do
    if curl -sf --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  return 1
}

# ── Service definitions ──────────────────────────────────────────
# name:host_port:health_path
SERVICES=(
  "discovery-server:8761:/actuator/health"
  "postgres-db:5432:"
  "user-service:8089:/actuator/health"
  "auth-service:8088:/actuator/health"
  "variant-service:8091:/actuator/health"
  "core-data-service:8092:/actuator/health"
  "api-gateway:8080:/actuator/health"
  "keycloak:8081:"
  "permission-service:8090:/actuator/health"
  "report-service:8095:/actuator/health"
  "schema-service:8096:/actuator/health"
)

# Zanzibar endpoints (no auth — expect 401/403, not connection refused)
ZANZIBAR_ENDPOINTS=(
  "permission-service|GET|http://localhost:8090/api/v1/authz/version"
  "permission-service|POST|http://localhost:8090/api/v1/permissions/check"
  "user-service|POST|http://localhost:8089/api/v1/authz/check"
  "core-data-service|POST|http://localhost:8092/api/v1/authz/check"
  "core-data-service|POST|http://localhost:8092/api/v1/authz/batch-check"
)

# ── Trap cleanup ─────────────────────────────────────────────────
trap cleanup EXIT

# ── Start services ───────────────────────────────────────────────
echo ">> Starting services from $COMPOSE_FILE ..."
docker compose -f "$COMPOSE_FILE" up -d --build 2>&1 | tail -5

echo ">> Waiting for services to become healthy (timeout: ${TIMEOUT}s each)..."

# ── Health checks ────────────────────────────────────────────────
for entry in "${SERVICES[@]}"; do
  IFS=: read -r name port path <<< "$entry"

  if [[ "$name" == "postgres-db" ]]; then
    # postgres uses pg_isready inside container
    elapsed=0
    healthy=false
    while [[ $elapsed -lt $TIMEOUT ]]; do
      if docker compose -f "$COMPOSE_FILE" exec -T postgres-db pg_isready -U postgres -d users >/dev/null 2>&1; then
        healthy=true; break
      fi
      sleep 2; elapsed=$((elapsed + 2))
    done
    if $healthy; then add_result "health:$name" "PASS" "pg_isready OK"
    else add_result "health:$name" "FAIL" "pg_isready timeout after ${TIMEOUT}s"; fi
    continue
  fi

  if [[ "$name" == "keycloak" ]]; then
    # keycloak health: TCP check on mapped port
    elapsed=0
    healthy=false
    while [[ $elapsed -lt $TIMEOUT ]]; do
      if curl -sf --max-time 3 "http://localhost:${port}/" >/dev/null 2>&1; then
        healthy=true; break
      fi
      sleep 2; elapsed=$((elapsed + 2))
    done
    if $healthy; then add_result "health:$name" "PASS" "HTTP reachable on :${port}"
    else add_result "health:$name" "FAIL" "not reachable on :${port} after ${TIMEOUT}s"; fi
    continue
  fi

  url="http://localhost:${port}${path}"
  if wait_for_health "$name" "$url"; then
    add_result "health:$name" "PASS" "$url OK"
  else
    add_result "health:$name" "FAIL" "$url unreachable after ${TIMEOUT}s"
  fi
done

# ── Zanzibar endpoint checks ────────────────────────────────────
echo ">> Testing Zanzibar endpoints..."

for entry in "${ZANZIBAR_ENDPOINTS[@]}"; do
  IFS='|' read -r svc method url <<< "$entry"
  label="zanzibar:${svc}:$(basename "$url")"

  if [[ "$method" == "GET" ]]; then
    http_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo "000")
  else
    http_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
      -X POST -H "Content-Type: application/json" -d '{}' "$url" 2>/dev/null || echo "000")
  fi

  # PASS = endpoint is wired (any HTTP response). FAIL = connection refused / timeout (000).
  if [[ "$http_code" != "000" ]]; then
    add_result "$label" "PASS" "HTTP $http_code (endpoint wired)"
  else
    add_result "$label" "FAIL" "connection refused or timeout"
  fi
done

# ── Write JSON report ───────────────────────────────────────────
END_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OVERALL="PASS"
[[ $FAIL_COUNT -gt 0 ]] && OVERALL="FAIL"

mkdir -p "$REPORT_DIR"

python3 -c "
import json, sys
report = {
    'schema': 'docker-smoke-result.v1',
    'timestamp': '$START_TS',
    'finished_at': '$END_TS',
    'timeout_seconds': $TIMEOUT,
    'overall': '$OVERALL',
    'pass_count': $PASS_COUNT,
    'fail_count': $FAIL_COUNT,
    'checks': json.loads('''$(printf '%s' "$RESULTS")''')
}
sys.stdout.write(json.dumps(report, indent=2) + '\n')
" > "$REPORT_FILE"

echo ""
echo ">> Result: $OVERALL (pass=$PASS_COUNT fail=$FAIL_COUNT)"
echo ">> Report: $REPORT_FILE"

[[ $FAIL_COUNT -gt 0 ]] && exit 1
exit 0
