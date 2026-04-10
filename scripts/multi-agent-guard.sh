#!/usr/bin/env bash
# multi-agent-guard.sh — Single SSOT guard for multi-agent git coordination
# Policy: policies/policy_multi_agent_coordination.v1.json (orchestrator)
#
# Called by: .githooks/pre-commit, .githooks/pre-push, .claude/settings.json hooks
# Pattern follows: CORE_UNLOCK + CORE_UNLOCK_REASON (existing repo SSOT)
#
# Usage:
#   bash scripts/multi-agent-guard.sh --op commit [--caller pre-commit]
#   bash scripts/multi-agent-guard.sh --op push [--caller pre-push]
#   bash scripts/multi-agent-guard.sh --op destructive [--caller settings-hook]
#
# Exit codes:
#   0 = allowed (worktree or single-worktree canonical or override)
#   1 = blocked (canonical tree with side worktrees, no valid override)
#   2 = usage error

set -euo pipefail

OP=""
CALLER="unknown"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --op) OP="$2"; shift 2;;
    --caller) CALLER="$2"; shift 2;;
    -h|--help)
      echo "Usage: bash scripts/multi-agent-guard.sh --op <commit|push|destructive> [--caller <name>]"
      exit 0;;
    *) echo "[multi-agent-guard] Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "${OP}" ]]; then
  echo "[multi-agent-guard] --op required (commit|push|destructive)" >&2
  exit 2
fi

# --- Worktree detection (authoritative) ---
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || true)"
GIT_COMMON="$(git rev-parse --git-common-dir 2>/dev/null || true)"

if [[ -z "${GIT_DIR}" || -z "${GIT_COMMON}" ]]; then
  echo "[multi-agent-guard] Not in a git repo" >&2
  exit 2
fi

# Linked worktree: git-dir != git-common-dir → ALLOWED (light mode)
if [[ "${GIT_DIR}" != "${GIT_COMMON}" ]]; then
  exit 0
fi

# --- Canonical tree: check side worktrees ---
WORKTREE_COUNT="$(git worktree list --porcelain 2>/dev/null | grep -c '^worktree ' || echo 1)"

if [[ "${WORKTREE_COUNT}" -le 1 ]]; then
  # Single worktree (only canonical) → ALLOWED
  exit 0
fi

# --- Canonical tree with side worktrees: check override ---
OVERRIDE_VAR=""
case "${OP}" in
  commit) OVERRIDE_VAR="ALLOW_CANONICAL_COMMIT";;
  push) OVERRIDE_VAR="ALLOW_CANONICAL_PUSH";;
  destructive) OVERRIDE_VAR="ALLOW_CANONICAL_DESTRUCTIVE";;
  *) echo "[multi-agent-guard] Unknown op: ${OP}" >&2; exit 2;;
esac

OVERRIDE_VALUE="${!OVERRIDE_VAR:-}"
OVERRIDE_REASON="${CANONICAL_OVERRIDE_REASON:-}"

if [[ -n "${OVERRIDE_VALUE}" ]]; then
  # Override requested — check REASON (MUST, follows CORE_UNLOCK_REASON pattern)
  if [[ -z "${OVERRIDE_REASON}" ]]; then
    echo "[multi-agent-guard] BLOCKED: Override istendi ama CANONICAL_OVERRIDE_REASON eksik." >&2
    echo "  Kullanim: ${OVERRIDE_VAR}=1 CANONICAL_OVERRIDE_REASON=\"hotfix\" git ${OP} ..." >&2
    exit 1
  fi

  # Override valid — write audit log
  LOG_DIR="$(git rev-parse --show-toplevel 2>/dev/null)/.cache/reports"
  LOG_FILE="${LOG_DIR}/canonical_override_log.v1.jsonl"
  mkdir -p "${LOG_DIR}" 2>/dev/null || true

  TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  ACTOR="$(whoami)"
  BRANCH="$(git branch --show-current 2>/dev/null || echo detached)"
  HEAD="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

  printf '{"timestamp":"%s","actor":"%s","op":"%s","branch":"%s","head":"%s","reason":"%s","caller":"%s","worktree_count":%s}\n' \
    "${TIMESTAMP}" "${ACTOR}" "${OP}" "${BRANCH}" "${HEAD}" "${OVERRIDE_REASON}" "${CALLER}" "${WORKTREE_COUNT}" \
    >>"${LOG_FILE}" 2>/dev/null || true

  echo "[multi-agent-guard] OVERRIDE: ${OP} izin verildi (reason=${OVERRIDE_REASON})"
  exit 0
fi

# --- BLOCKED ---
echo "[multi-agent-guard] BLOCKED: Canonical tree'de ${OP} yasak." >&2
echo "  Aktif worktree sayisi: ${WORKTREE_COUNT}" >&2
echo "  Worktree ac: git worktree add /path -b feat/<agent>-<task> main" >&2
echo "  Mevcut worktree'ler: git worktree list" >&2
echo "" >&2
echo "  Override (acil, inline):" >&2
echo "    ${OVERRIDE_VAR}=1 CANONICAL_OVERRIDE_REASON=\"<neden>\" git ${OP} ..." >&2
echo "  NOT: export ile kalici acma YASAK. Inline kullanin." >&2
exit 1
