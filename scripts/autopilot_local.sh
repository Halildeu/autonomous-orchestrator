#!/usr/bin/env bash
set -euo pipefail

# Prevent accidental secret leakage if the caller enabled xtrace.
set +x

REPO="${GITHUB_REPOSITORY:-}"
PR=""
MAX_ATTEMPTS=5
OUT_DIR="artifacts/ci-logs"

FIX_CMD="${AUTOPILOT_FIX_CMD:-}"
ANY_FAIL="${AUTOPILOT_ANY_FAIL:-}"
AUTO_CONFLICT="${AUTOPILOT_AUTO_CONFLICT:-}"

SEMANTIC_LINT_ENABLED="${AUTOPILOT_SEMANTIC_LINT:-}"
SEMANTIC_JSON_OUT="${AUTOPILOT_SEMANTIC_JSON_OUT:-.autopilot-tmp/doc-lint/semantic-report.json}"
SEMANTIC_TSV_OUT="${AUTOPILOT_SEMANTIC_TSV_OUT:-.autopilot-tmp/doc-lint/semantic-report.tsv}"

usage() {
  echo "Usage: $0 --pr <num> [--repo owner/repo] [--max N] [--out dir]"
  echo "Env: GH_TOKEN must be set or gh auth login; token value not printed."
  echo "Env: AUTOPILOT_FIX_CMD optional (command that applies a fix locally)."
  echo "Env: AUTOPILOT_ANY_FAIL=1 optional (treat any failing check as failure; default watches required checks only)."
  echo "Env: AUTOPILOT_AUTO_CONFLICT=1 optional (mergeable_state=dirty ise main ile auto-resolve dener; allowlist scope)."
  echo "Env: AUTOPILOT_SEMANTIC_LINT=1 optional (local-only semantic lint report)."
  echo "Guard: git push oncesi scripts/require_local_gate.sh --auto-run zorunlu calisir."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --pr) PR="$2"; shift 2;;
    --max) MAX_ATTEMPTS="$2"; shift 2;;
    --out) OUT_DIR="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if [[ -z "${REPO}" || -z "${PR}" ]]; then
  usage; exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "[autopilot] gh CLI not found. Install gh or set PATH."
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${script_dir}/ops/gh_token_preflight.sh" ]; then
  # shellcheck source=/dev/null
  source "${script_dir}/ops/gh_token_preflight.sh"
fi
if ! gh api rate_limit >/dev/null 2>&1; then
  gh_token_preflight >/dev/null 2>&1 || {
    echo "[autopilot] GH auth unavailable. Fix: set GH_TOKEN/GITHUB_TOKEN (or GH_AUTH_VAULT_PATH/FIELD) and retry."
    exit 2
  }
fi

# If this script checks out other refs, make sure we can return to the starting ref
# so the ops scripts remain available in the worktree.
BASE_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
cleanup_restore_branch() {
  if [[ -z "${BASE_BRANCH}" ]]; then
    return 0
  fi

  # Only restore if worktree is clean; otherwise keep state for debugging.
  if git diff --quiet && git diff --cached --quiet; then
    git checkout "${BASE_BRANCH}" >/dev/null 2>&1 || true
  fi
}
trap cleanup_restore_branch EXIT

PR_JSON="$(gh api "repos/${REPO}/pulls/${PR}" 2>/dev/null || true)"
if [[ -z "${PR_JSON}" ]]; then
  echo "[autopilot] Cannot read PR JSON."
  exit 2
fi

HEAD_REF="$(
  python3 -c 'import json,sys; print((json.load(sys.stdin).get("head",{}) or {}).get("ref",""))' <<<"${PR_JSON}"
)"
if [[ -z "${HEAD_REF}" ]]; then
  echo "[autopilot] Cannot read PR head ref."
  exit 2
fi

PR_STATE="$(
  python3 -c 'import json,sys; print((json.load(sys.stdin).get("state") or "").strip())' <<<"${PR_JSON}"
)"
PR_STATE_LC="$(printf '%s' "${PR_STATE}" | tr '[:upper:]' '[:lower:]')"
if [[ -n "${PR_STATE_LC}" && "${PR_STATE_LC}" != "open" ]]; then
  echo "[autopilot] PR is not open (state=${PR_STATE}); noop."
  exit 0
fi

echo "[autopilot] repo=${REPO} pr=#${PR} head_ref=${HEAD_REF} max=${MAX_ATTEMPTS}"
if [[ "${ANY_FAIL}" == "1" ]]; then
  echo "[autopilot] mode=any-fail (all checks)"
else
  echo "[autopilot] mode=required-only (default)"
fi

if [[ "${AUTO_CONFLICT}" == "1" ]]; then
  MERGEABLE_STATE="$(
    python3 -c 'import json,sys; print((json.load(sys.stdin).get("mergeable_state") or "").strip())' <<<"${PR_JSON}"
  )"
  if [[ "${MERGEABLE_STATE}" == "dirty" ]]; then
    echo "[autopilot] mergeable_state=dirty -> attempting auto conflict resolve with main..."
    if ! python3 scripts/resolve_merge_conflicts.py --repo "${REPO}" --pr "${PR}"; then
      RC=$?
      if [[ $RC -eq 4 ]]; then
        echo "[autopilot] STOP: conflict auto-resolve done but local ci-gate validate FAILED (needs-human)."
      else
        echo "[autopilot] STOP: auto conflict resolve failed (needs-human) rc=${RC}."
      fi
      exit 6
    fi
  fi
fi

collect_changed_docs() {
  {
    git diff --name-only
    git diff --name-only --cached
    git diff --name-only origin/main...HEAD 2>/dev/null || true
  } | grep -E '^docs/' | grep -E '\.md$' | sort -u
}

maybe_semantic_lint() {
  if [[ "${SEMANTIC_LINT_ENABLED}" != "1" ]]; then
    return 0
  fi

  local changed_docs
  changed_docs="$(collect_changed_docs || true)"
  if [[ -z "${changed_docs}" ]]; then
    echo "[autopilot] semantic-lint: no docs changes detected; skip"
    return 0
  fi

  echo "[autopilot] semantic-lint: running (non-blocking)"
  python3 scripts/check_doc_semantic_lint.py \
    --paths ${changed_docs} \
    --json-out "${SEMANTIC_JSON_OUT}" \
    --tsv-out "${SEMANTIC_TSV_OUT}" \
    >/dev/null 2>&1 || true

  SEMANTIC_JSON_OUT="${SEMANTIC_JSON_OUT}" python3 - <<'PY' || true
import json
import os
from pathlib import Path

json_out = Path(os.environ.get("SEMANTIC_JSON_OUT", ".autopilot-tmp/doc-lint/semantic-report.json"))
if not json_out.exists():
    raise SystemExit(0)

d = json.loads(json_out.read_text(encoding="utf-8"))
s = d.get("summary") or {}
sc = s.get("severity_counts") or {}
avg = s.get("avg_score")

files = d.get("files") or []
lowest = sorted((f.get("score", 0), f.get("path", "")) for f in files)[:3]

print("[autopilot] semantic-lint: avg_score=", avg, "counts=", sc)
if lowest:
    print("[autopilot] semantic-lint: lowest=", ", ".join(f"{p}:{score}" for score, p in lowest if p))
PY
}

wait_for_workflows() {
  local head_sha="$1"
  local mode="$2" # required|any

  local max_wait_sec="${AUTOPILOT_WAIT_MAX_SEC:-1800}"
  local sleep_sec="${AUTOPILOT_WAIT_INTERVAL_SEC:-10}"
  local start_ts
  start_ts="$(date +%s)"

  local out_dir="${OUT_DIR}/pr-${PR}"
  mkdir -p "${out_dir}"
  local runs_pages="${out_dir}/runs-pages.json"

  while true; do
    gh api --paginate --slurp \
      "repos/${REPO}/actions/runs?event=pull_request&head_sha=${head_sha}&per_page=100" \
      > "${runs_pages}"

    local py_rc=0
    python3 - "${runs_pages}" "${mode}" <<'PY' || py_rc=$?
import json
import sys

path = sys.argv[1]
mode = sys.argv[2]

pages = json.load(open(path, "r", encoding="utf-8"))
if not isinstance(pages, list):
    pages = [pages]

all_runs = []
for page in pages:
    if not isinstance(page, dict):
        continue
    runs = page.get("workflow_runs") or []
    if isinstance(runs, list):
        all_runs.extend([r for r in runs if isinstance(r, dict)])

# Newest-first already; pick latest run per workflow name.
latest_by_name = {}
for r in all_runs:
    name = r.get("name")
    if not isinstance(name, str) or not name.strip():
        continue
    if name in latest_by_name:
        continue
    latest_by_name[name] = r

ci = latest_by_name.get("ci-gate")
if not isinstance(ci, dict):
    print("[autopilot] ci-gate: missing (waiting)")
    raise SystemExit(2)

ci_status = ci.get("status") or ""
ci_conclusion = ci.get("conclusion") or ""
ci_url = ci.get("html_url") or ""

if ci_status != "completed":
    print(f"[autopilot] ci-gate: {ci_status} (waiting) {ci_url}")
    raise SystemExit(2)

def ok_conclusion(c: str) -> bool:
    # "neutral"/"skipped" are not failures for our local loop.
    return c in ("success", "neutral", "skipped", "")

pending = []
failing = []
for name, r in latest_by_name.items():
    status = r.get("status") or ""
    if status != "completed":
        pending.append(name)
        continue
    conclusion = str(r.get("conclusion") or "")
    if not ok_conclusion(conclusion):
        failing.append(name)

pending.sort()
failing.sort()

if mode == "any":
    if pending:
        print(f"[autopilot] pending workflows: {', '.join(pending)} (waiting)")
        raise SystemExit(2)
    if failing:
        print(f"[autopilot] FAIL workflows: {', '.join(failing)}")
        raise SystemExit(1)
    print(f"[autopilot] PASS all workflows (ci-gate={ci_conclusion})")
    raise SystemExit(0)

# required-only: only ci-gate matters
if ci_conclusion == "success":
    print(f"[autopilot] PASS ci-gate {ci_url}")
    raise SystemExit(0)

print(f"[autopilot] FAIL ci-gate (conclusion={ci_conclusion}) {ci_url}")
raise SystemExit(1)
PY
    if [[ $py_rc -ne 2 ]]; then
      return $py_rc
    fi

    local now_ts
    now_ts="$(date +%s)"
    if (( now_ts - start_ts >= max_wait_sec )); then
      echo "[autopilot] STOP: wait timeout (${max_wait_sec}s) for workflows on head_sha=${head_sha}"
      return 7
    fi
    sleep "${sleep_sec}"
  done
}

# Local PR tracker (gitignored). No-op on errors.
python3 scripts/pr_tracker_tsv.py --repo "${REPO}" add --pr "${PR}" >/dev/null 2>&1 || true

# Checkout PR head safely (worktree-friendly):
# - Do NOT checkout the PR branch name directly, because it may be checked out in another worktree.
# - Also avoid using a fixed local scratch branch name, because it can be checked out in another worktree too.
# - Use a worktree-specific scratch branch and push back to the original PR branch ref explicitly.
WORKTREE_TAG="$(basename "$(pwd)" | tr -c '[:alnum:]._-' '-')"
WORKTREE_TAG="$(printf '%s' "${WORKTREE_TAG}" | sed -E 's/^-+//; s/-+$//')"
if [[ -z "${WORKTREE_TAG}" ]]; then
  WORKTREE_TAG="wt"
fi
SCRATCH_BRANCH="autopilot/pr-${PR}-${WORKTREE_TAG}"
REMOTE_REF="origin/${HEAD_REF}"

git fetch --all --prune
if ! git show-ref --verify --quiet "refs/remotes/${REMOTE_REF}"; then
  echo "[autopilot] remote ref not found: ${REMOTE_REF}; noop."
  exit 0
fi

git checkout -B "${SCRATCH_BRANCH}" "${REMOTE_REF}"

attempt=1
while [[ $attempt -le $MAX_ATTEMPTS ]]; do
  PR_JSON="$(gh api "repos/${REPO}/pulls/${PR}" 2>/dev/null || true)"
  HEAD_SHA="$(
    python3 -c 'import json,sys; print((json.load(sys.stdin).get("head",{}) or {}).get("sha",""))' <<<"${PR_JSON}"
  )"
  if [[ -z "${HEAD_SHA}" ]]; then
    echo "[autopilot] Cannot read PR head sha."
    exit 2
  fi

  MODE="required"
  [[ "${ANY_FAIL}" == "1" ]] && MODE="any"

  echo "[autopilot] attempt ${attempt}/${MAX_ATTEMPTS}: waiting workflows for head_sha=${HEAD_SHA:0:7}..."
  if wait_for_workflows "${HEAD_SHA}" "${MODE}"; then
    state="$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("state") or "unknown"))' <<<"${PR_JSON}" 2>/dev/null || echo unknown)"
    echo "[autopilot] PASS. PR state=${state}"
    python3 scripts/pr_tracker_tsv.py --repo "${REPO}" add --pr "${PR}" >/dev/null 2>&1 || true
    maybe_semantic_lint || true
    exit 0
  fi

  RC=$?
  if [[ $RC -ne 1 ]]; then
    exit "$RC"
  fi

  echo "[autopilot] FAIL. downloading logs..."
  ./scripts/ci_pull_logs.sh --repo "${REPO}" --pr "${PR}" --out "${OUT_DIR}" || true
  FAILURE_MD="${OUT_DIR}/pr-${PR}/FAILURE.md"
  echo "[autopilot] failure bundle: ${FAILURE_MD}"
  python3 scripts/pr_tracker_tsv.py --repo "${REPO}" add --pr "${PR}" >/dev/null 2>&1 || true

  if [[ -z "${FIX_CMD}" ]]; then
    echo "[autopilot] No AUTOPILOT_FIX_CMD set. Stop here so you can run Codex manually using FAILURE.md."
    exit 3
  fi

  BEFORE_SHA="$(git rev-parse HEAD)"
  echo "[autopilot] running fix command (token not printed)..."
  export FAILURE_MD
  bash -lc "${FIX_CMD}"
  AFTER_SHA="$(git rev-parse HEAD)"

  if git diff --quiet && git diff --cached --quiet; then
    if [[ "${AFTER_SHA}" != "${BEFORE_SHA}" ]]; then
      echo "[autopilot] fix command created a commit (no working tree diff)."
    else
      echo "[autopilot] no changes after fix. stopping."
      exit 4
    fi
  fi

  maybe_semantic_lint || true

  if ! (git diff --quiet && git diff --cached --quiet); then
    bash scripts/require_local_gate.sh --auto-run --caller autopilot-local
    git add -A
    git commit -m "fix(autopilot): attempt ${attempt} for PR #${PR}" || true
  fi

  bash scripts/require_local_gate.sh --auto-run --caller autopilot-local
  git push -u origin HEAD:"${HEAD_REF}"
  python3 scripts/pr_tracker_tsv.py --repo "${REPO}" add --pr "${PR}" >/dev/null 2>&1 || true
  attempt=$((attempt+1))
done

echo "[autopilot] max attempts reached; stopping."
exit 5
