#!/usr/bin/env bash
# shellcheck shell=bash

set -euo pipefail

ORCHESTRATOR_ROOT="$(pwd)"
WORKSPACE_ROOT_PREFIX=""
MANAGED_ROOTS_CRITICAL="${MANAGED_ROOTS_CRITICAL:-true}"

if [ "$#" -eq 0 ]; then
  echo "Kullanim:"
  echo "  ./scripts/run_phase_all_clean.sh --orchestrator-root <path> --managed-repo-root <path> --workspace-root-prefix <path> [ek args]"
  exit 1
fi

index=1
while [ "$index" -le "$#" ]; do
  arg="${!index}"
  case "$arg" in
    --orchestrator-root)
      index=$((index + 1))
      if [ "$index" -le "$#" ]; then
        ORCHESTRATOR_ROOT="${!index}"
      fi
      ;;
    --orchestrator-root=*)
      ORCHESTRATOR_ROOT="${arg#*=}"
      ;;
    --workspace-root-prefix)
      index=$((index + 1))
      if [ "$index" -le "$#" ]; then
        WORKSPACE_ROOT_PREFIX="${!index}"
      fi
      ;;
    --workspace-root-prefix=*)
      WORKSPACE_ROOT_PREFIX="${arg#*=}"
      ;;
  esac
  index=$((index + 1))
done

if [ -z "$WORKSPACE_ROOT_PREFIX" ]; then
  WORKSPACE_ROOT_PREFIX="${ORCHESTRATOR_ROOT}/.cache/ws_customer_default_multi2"
fi

if [ -d "$WORKSPACE_ROOT_PREFIX" ]; then
  find "$WORKSPACE_ROOT_PREFIX" -type f \
    \( -path "*/.cache/repo_hygiene/report.json" -o -path "*/.cache/roadmap_actions.v1.json" \) \
    -delete
fi

python3 "${ORCHESTRATOR_ROOT}/scripts/run_project_management_3phases.py" \
  "$@" \
  --phase all \
  --critical-only true \
  --print-evidence-map false \
  --managed-roots-critical "${MANAGED_ROOTS_CRITICAL}"
