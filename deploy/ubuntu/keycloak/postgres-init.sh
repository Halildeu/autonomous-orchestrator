#!/usr/bin/env bash
set -euo pipefail

echo "[postgres-init] waiting for postgres..."
until pg_isready -h postgres -U appuser -d postgres >/dev/null 2>&1; do
  sleep 1
done

ROLE="${KC_DB_USERNAME}"
PASS="${KC_DB_PASSWORD}"

echo "[postgres-init] ensuring role ${ROLE} exists..."
psql -h postgres -U appuser -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='${ROLE}'" | grep -q 1 \
  || psql -h postgres -U appuser -d postgres -c "CREATE ROLE \"${ROLE}\" LOGIN PASSWORD '${PASS}';"

echo "[postgres-init] ensuring database keycloak exists..."
psql -h postgres -U appuser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='keycloak'" | grep -q 1 \
  || psql -h postgres -U appuser -d postgres -c "CREATE DATABASE keycloak OWNER \"${ROLE}\";"

echo "[postgres-init] done."
