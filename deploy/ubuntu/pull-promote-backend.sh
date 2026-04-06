#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-/home/halil/platform/repo}"
ENV_FILE="${ENV_FILE:-/home/halil/platform/env/backend.env.prod}"
COMPOSE_PROFILES="${COMPOSE_PROFILES:-}"
DEPLOY_ENV="${DEPLOY_ENV:-prod}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
RENDER_ENV_BEFORE_DEPLOY="${RENDER_ENV_BEFORE_DEPLOY:-true}"

REPO_DIR="${REPO_DIR}" \
ENV_FILE="${ENV_FILE}" \
COMPOSE_PROFILES="${COMPOSE_PROFILES}" \
DEPLOY_ENV="${DEPLOY_ENV}" \
VAULT_ADDR="${VAULT_ADDR}" \
RENDER_ENV_BEFORE_DEPLOY="${RENDER_ENV_BEFORE_DEPLOY}" \
exec "${SCRIPT_DIR}/deploy-backend.sh"
