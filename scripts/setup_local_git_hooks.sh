#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT_DIR}" ]]; then
  echo "[local-gate-hooks] git repo bulunamadi." >&2
  exit 2
fi

cd "${ROOT_DIR}"
chmod +x .githooks/pre-commit .githooks/pre-push scripts/require_local_gate.sh scripts/run_local_gate_chain.sh scripts/ops/load_local_env.sh
git config core.hooksPath .githooks
echo "[local-gate-hooks] core.hooksPath=.githooks"
echo "[local-gate-hooks] canonical runner: scripts/run_local_gate_chain.sh"
echo "[local-gate-hooks] canonical guard: scripts/require_local_gate.sh"
echo "[local-gate-hooks] PASS artifact: .cache/reports/local-gate-chain/status.json"
