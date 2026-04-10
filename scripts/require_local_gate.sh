#!/usr/bin/env bash
set -euo pipefail

set +x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKTREE_MODE="${LOCAL_GATE_WORKTREE_MODE:-0}"
AUTO_RUN=0
CALLER="manual"

# In worktree mode, use the worktree's own .cache (not canonical)
if [[ "${WORKTREE_MODE}" == "1" ]]; then
  WORKTREE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  STATUS_PATH="${LOCAL_GATE_STATUS_PATH:-${WORKTREE_ROOT}/.cache/reports/local-gate-chain/status.json}"
else
  STATUS_PATH="${LOCAL_GATE_STATUS_PATH:-${ROOT_DIR}/.cache/reports/local-gate-chain/status.json}"
fi

usage() {
  cat <<'EOF'
Usage: bash scripts/require_local_gate.sh [--auto-run] [--caller <name>] [--worktree-mode]

- PASS artifact varsa ve mevcut worktree fingerprint ile eslesiyorsa 0 doner.
- Aksi halde --auto-run verilmis ise local gate zincirini calistirir.
- --worktree-mode: linked worktree'de light gate chain + staged-only fingerprint.
- Gecerli artifact olmadan commit/push devam etmemelidir.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto-run) AUTO_RUN=1; shift 1;;
    --caller) CALLER="$2"; shift 2;;
    --worktree-mode) WORKTREE_MODE=1; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "[local-gate-guard] Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

compute_worktree_fingerprint() {
  if [[ "${WORKTREE_MODE}" == "1" ]]; then
    # Reduced fingerprint: staged diff + staged paths + HEAD + branch + worktree_id
    python3 "${SCRIPT_DIR}/ops/compute_worktree_fingerprint.py" \
      --repo-root "${WORKTREE_ROOT:-${ROOT_DIR}}" --staged-only
  else
    python3 "${SCRIPT_DIR}/ops/compute_worktree_fingerprint.py" --repo-root "${ROOT_DIR}"
  fi
}

validate_artifact() {
  local current_head current_branch current_fp
  current_head="$(git rev-parse HEAD)"
  current_branch="$(git branch --show-current)"
  current_fp="$(compute_worktree_fingerprint)"

  python3 - "${STATUS_PATH}" "${current_head}" "${current_branch}" "${current_fp}" <<'PY'
import json
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
current_head = sys.argv[2]
current_branch = sys.argv[3]
current_fp = sys.argv[4]

if not status_path.exists():
    print("[local-gate-guard] status.json bulunamadi.", file=sys.stderr)
    raise SystemExit(1)

data = json.loads(status_path.read_text(encoding="utf-8"))
overall = str(data.get("overall_status") or "").upper()
saved_head = str(data.get("head_sha") or "")
saved_branch = str(data.get("branch") or "")
saved_fp = str(data.get("worktree_fingerprint") or "")

if overall != "PASS":
    print(f"[local-gate-guard] artifact PASS degil: {overall or 'UNKNOWN'}", file=sys.stderr)
    raise SystemExit(1)

if saved_head != current_head:
    print("[local-gate-guard] HEAD degisti; gate artifact stale.", file=sys.stderr)
    raise SystemExit(1)

if saved_branch != current_branch:
    print("[local-gate-guard] branch degisti; gate artifact stale.", file=sys.stderr)
    raise SystemExit(1)

if saved_fp != current_fp:
    print("[local-gate-guard] worktree fingerprint degisti; local gate yeniden kosmali.", file=sys.stderr)
    raise SystemExit(1)

print("[local-gate-guard] PASS")
PY
}

# In worktree mode, cd to worktree root; otherwise canonical root
if [[ "${WORKTREE_MODE}" == "1" ]]; then
  cd "${WORKTREE_ROOT:-${ROOT_DIR}}"
else
  cd "${ROOT_DIR}"
fi

if validate_artifact >/dev/null 2>&1; then
  echo "[local-gate-guard] PASS (${CALLER})"
  exit 0
fi

if [[ "${AUTO_RUN}" != "1" ]]; then
  echo "[local-gate-guard] FAIL (${CALLER}) - gecerli local gate artifact yok." >&2
  echo "[local-gate-guard] once: bash scripts/run_local_gate_chain.sh" >&2
  exit 1
fi

echo "[local-gate-guard] stale/missing artifact -> local gate zinciri calistiriliyor (${CALLER})"

if [[ "${WORKTREE_MODE}" == "1" ]]; then
  # Light mode gate chain for worktrees
  bash "${SCRIPT_DIR}/run_local_gate_chain.sh" --light
else
  bash "${SCRIPT_DIR}/run_local_gate_chain.sh"
fi

validate_artifact >/dev/null
echo "[local-gate-guard] PASS (${CALLER})"
