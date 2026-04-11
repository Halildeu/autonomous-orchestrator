#!/usr/bin/env bash
set -euo pipefail

# Setup local git hooks for pre-push gate enforcement.
# Run once: bash scripts/setup_local_git_hooks.sh

cd "${ROOT_DIR}"
chmod +x .githooks/pre-commit .githooks/pre-push scripts/require_local_gate.sh scripts/run_local_gate_chain.sh scripts/ops/load_local_env.sh
git config core.hooksPath .githooks
echo "[local-gate-hooks] core.hooksPath=.githooks"
echo "[local-gate-hooks] canonical runner: scripts/run_local_gate_chain.sh"
echo "[local-gate-hooks] canonical guard: scripts/require_local_gate.sh"
echo "[local-gate-hooks] PASS artifact: .cache/reports/local-gate-chain/status.json"
