#!/usr/bin/env bash
set -euo pipefail

# Prevent accidental secret leakage if the caller enabled xtrace.
set +x

REPO="${GITHUB_REPOSITORY:-}"
BASE_BRANCH="main"
HEAD_BRANCH=""
PR_NUMBER=""

MAX_FIX_ATTEMPTS=5
OUT_DIR="artifacts/ci-logs"

FIX_MODE="manual" # manual|auto
FIX_CMD="${AUTOPILOT_FIX_CMD:-}"
ANY_FAIL="${AUTOPILOT_ANY_FAIL:-0}"
AUTO_CONFLICT="${AUTOPILOT_AUTO_CONFLICT:-0}"

MERGE_MODE="auto" # auto|direct|skip
FORCE_MERGE="0"
MERGE_WAIT_SEC=180
DELETE_BRANCH="0"
ALLOW_DIRECT_MERGE="${ALLOW_DIRECT_MERGE:-0}" # 0|1 (hard guardrail)

# Merge-bot dispatch fallback (default ON; direct merge still break-glass).
MERGE_BOT_DISPATCH="${MERGE_BOT_DISPATCH:-1}" # 0|1
MERGE_BOT_DISPATCH_REF="${MERGE_BOT_DISPATCH_REF:-main}"
MERGE_BOT_DISPATCH_WORKFLOW_FILE="${MERGE_BOT_DISPATCH_WORKFLOW_FILE:-pr-merge.yml}"
MERGE_BOT_DISPATCH_WAIT_SEC="${MERGE_BOT_DISPATCH_WAIT_SEC:-120}"
MERGE_BOT_DISPATCH_CONFIRM="MERGE"

DEPLOY_MODE="auto" # auto|dispatch|skip
DEPLOY_ENV="stage"
DEPLOY_TRIGGER_WAIT_SEC=120
DEPLOY_WAIT_MAX_SEC=2400

usage() {
  cat <<'EOF'
Usage: bash scripts/ops/local_merge_deploy_orchestrator.sh [options]

Goal (local SSOT):
- Ensure PR exists
- Wait/fix CI locally (via scripts/autopilot_local.sh)
- Merge (default: bot; direct merge only if explicitly allowed)
- Deploy (GitHub Actions) + watch validate/rollback
- Pull logs for deploy chain

Options:
  --repo owner/repo            (default: detect from origin remote or env GITHUB_REPOSITORY)
  --base main                  (default: main)
  --head <branch>              (default: current git branch)
  --pr <num>                   (default: find/create PR for --head)

  --fix-mode manual|auto       (default: manual)
  --fix-cmd "<cmd>"            (only if fix-mode=auto; overrides AUTOPILOT_FIX_CMD)
  --max-fix N                  (default: 5)
  --any-fail 0|1               (default: 0; 1 => watch all workflows, not only ci-gate)
  --auto-conflict 0|1          (default: 0; 1 => try local conflict auto-resolve)

  --merge auto|direct|skip     (default: auto)
  --merge-wait-sec N           (default: 180; auto mode wait for merge-bot)
  --allow-direct-merge         (explicitly allow direct merge fallback / --merge direct)
  --force-merge                (override merge_policy=none)
  --delete-branch              (delete remote branch after merge; only for direct merge)

  --deploy auto|dispatch|skip  (default: auto)
  --deploy-env stage|prod      (informational; passed to workflow_dispatch inputs)
  --deploy-trigger-wait-sec N  (default: 120; wait for push-triggered deploy runs before dispatch fallback)
  --deploy-wait-max-sec N      (default: 2400; max wait for deploy/validate/rollback completion)

Notes:
- Token values are never printed.
- Deploy runs on GitHub Actions (recommended).
- Merge-bot dispatch fallback:
  - export MERGE_BOT_DISPATCH=1
  - export MERGE_BOT_DISPATCH_REF=main
  - export MERGE_BOT_DISPATCH_WORKFLOW_FILE=pr-merge.yml
EOF
}

die() { echo "[local-e2e] ERROR: $*" >&2; exit 2; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "missing command: $1"
  fi
}

detect_repo_from_origin() {
  local origin
  origin="$(git remote get-url origin 2>/dev/null || true)"
  if [[ "${origin}" =~ github\.com[:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
    local owner="${BASH_REMATCH[1]}"
    local repo="${BASH_REMATCH[2]}"
    repo="${repo%.git}"
    echo "${owner}/${repo}"
    return 0
  fi
  return 1
}

gh_ensure_auth() {
  if gh api rate_limit >/dev/null 2>&1; then
    return 0
  fi

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  # SSOT: Auth is OK if `gh api rate_limit` works (persist login OR env/Vault token).
  if [ -f "${script_dir}/gh_token_preflight.sh" ]; then
    # shellcheck source=/dev/null
    source "${script_dir}/gh_token_preflight.sh"
    gh_token_preflight >/dev/null 2>&1 || true
  fi

  if gh api rate_limit >/dev/null 2>&1; then
    return 0
  fi

  # Fallback: try persisting auth via gh (keychain/env/vault) if available.
  if [ -f "${script_dir}/gh_auth_with_token.sh" ]; then
    bash "${script_dir}/gh_auth_with_token.sh" >/dev/null 2>&1 || true
  fi

  if ! gh api rate_limit >/dev/null 2>&1; then
    die "gh token auth not available. Ensure GH_TOKEN/GITHUB_TOKEN is set (or GH_AUTH_VAULT_PATH/FIELD is configured), then retry."
  fi
}

git_setup_push_auth_best_effort() {
  if [ -f "scripts/ops/git_setup_push_auth.sh" ]; then
    bash scripts/ops/git_setup_push_auth.sh >/dev/null 2>&1 || true
  fi
}

pr_find_open_for_head() {
  local repo="$1"
  local head="$2"
  gh pr list --repo "${repo}" --head "${head}" --state open --json number,url \
    | python3 - <<'PY'
import json,sys
try:
    data=json.load(sys.stdin)
except Exception:
    data=[]
if not isinstance(data, list) or not data:
    print("")
    raise SystemExit(0)
pr=data[0] if isinstance(data[0], dict) else {}
n=pr.get("number")
print(str(n) if isinstance(n,int) else "")
PY
}

pr_create() {
  local repo="$1"
  local base="$2"
  local head="$3"
  local title="$4"
  local body_file="${5:-}"

  # Ensure remote branch exists
  git push -u origin "${head}" >/dev/null 2>&1 || true

  if [[ -n "${body_file}" && -f "${body_file}" ]]; then
    gh pr create --repo "${repo}" --base "${base}" --head "${head}" --title "${title}" --body-file "${body_file}" >/dev/null
  else
    gh pr create --repo "${repo}" --base "${base}" --head "${head}" --title "${title}" --body "Local SSOT: PR created via CLI (copy-free). See local execution-log for evidence." >/dev/null
  fi
}

merge_policy_for_branch() {
  local head_branch="$1"
  python3 - "${head_branch}" <<'PY'
import fnmatch
import json
import sys
from pathlib import Path

branch = sys.argv[1]
path = Path("docs-ssot/04-operations/PR-BOT-RULES.json")
if not path.exists():
    print("unknown")
    raise SystemExit(0)

cfg = json.loads(path.read_text(encoding="utf-8"))
rules = cfg.get("rules") or []
if not isinstance(rules, list):
    print("unknown")
    raise SystemExit(0)

def matches(pattern: str, value: str) -> bool:
    if pattern == value:
        return True
    return fnmatch.fnmatch(value, pattern)

for r in rules:
    if not isinstance(r, dict):
        continue
    m = r.get("match")
    if not isinstance(m, str) or not m.strip():
        continue
    if matches(m.strip(), branch):
        mp = r.get("merge_policy")
        if isinstance(mp, str) and mp.strip():
            print(mp.strip())
            raise SystemExit(0)

print("unknown")
PY
}

pr_get_meta() {
  local repo="$1"
  local pr="$2"
  gh api "repos/${repo}/pulls/${pr}" 2>/dev/null || echo "{}"
}

pr_is_merged() {
  python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
merged = d.get("merged_at") is not None
state = str(d.get("state") or "")
print("1" if merged and state.lower() == "closed" else "0")
PY
}

pr_merge_commit_sha() {
  python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
sha=d.get("merge_commit_sha")
print(sha or "")
PY
}

pr_mergeable_state() {
  python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
st=d.get("mergeable_state")
print(st or "")
PY
}

wait_for_pr_merged() {
  local repo="$1"
  local pr="$2"
  local max_sec="$3"
  local start
  start="$(date +%s)"

  while true; do
    local meta
    meta="$(pr_get_meta "${repo}" "${pr}")"
    if [[ "$(printf '%s' "${meta}" | pr_is_merged)" == "1" ]]; then
      printf '%s' "${meta}"
      return 0
    fi

    local now
    now="$(date +%s)"
    if (( now - start >= max_sec )); then
      return 1
    fi
    sleep 5
  done
}

dispatch_merge_bot() {
  local repo="$1"
  local pr="$2"
  local ref="$3"

  # Token is never printed; gh handles auth.
  gh api -X POST "repos/${repo}/actions/workflows/${MERGE_BOT_DISPATCH_WORKFLOW_FILE}/dispatches" \
    -f "ref=${ref}" \
    -f "inputs[pr_number]=${pr}" \
    -f "inputs[confirm]=${MERGE_BOT_DISPATCH_CONFIRM}" >/dev/null
}

changed_flags_for_head() {
  git fetch origin >/dev/null 2>&1 || true
  git diff --name-only "origin/${BASE_BRANCH}...HEAD" 2>/dev/null \
    | python3 - <<'PY'
import sys
paths=[l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
web = any(p.startswith("web/") or p == ".github/workflows/deploy-web.yml" for p in paths)
backend = any(p.startswith("backend/") or p == ".github/workflows/deploy-backend.yml" for p in paths)
print(("web=1" if web else "web=0") + " " + ("backend=1" if backend else "backend=0"))
PY
}

find_run_id_by_name_and_sha() {
  local repo="$1"
  local sha="$2"
  local name="$3"
  gh api --paginate --slurp "repos/${repo}/actions/runs?head_sha=${sha}&per_page=100" 2>/dev/null \
    | python3 - "${name}" <<'PY'
import json, sys
name = sys.argv[1]
pages = json.load(sys.stdin)
if not isinstance(pages, list):
    pages = [pages]
all_runs=[]
for page in pages:
    if not isinstance(page, dict):
        continue
    runs = page.get("workflow_runs") or []
    if isinstance(runs, list):
        all_runs.extend([r for r in runs if isinstance(r, dict)])
for r in all_runs:
    if r.get("name") == name:
        rid = r.get("id")
        print(rid if isinstance(rid, int) else "")
        raise SystemExit(0)
print("")
PY
}

wait_run_completed() {
  local repo="$1"
  local run_id="$2"
  local max_sec="$3"
  local start
  start="$(date +%s)"
  while true; do
    local run
    run="$(gh api "repos/${repo}/actions/runs/${run_id}" 2>/dev/null || echo '{}')"
    local status
    status="$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("status") or ""))' <<<"${run}")"
    if [[ "${status}" == "completed" ]]; then
      printf '%s' "${run}"
      return 0
    fi
    local now
    now="$(date +%s)"
    if (( now - start >= max_sec )); then
      return 1
    fi
    sleep 10
  done
}

run_conclusion_ok() {
  python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
c=(d.get("conclusion") or "")
print("1" if c in ("success","neutral","skipped","") else "0")
PY
}

run_html_url() {
  python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
print(d.get("html_url") or "")
PY
}

run_conclusion() {
  python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
print(d.get("conclusion") or "")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --base) BASE_BRANCH="$2"; shift 2;;
    --head) HEAD_BRANCH="$2"; shift 2;;
    --pr) PR_NUMBER="$2"; shift 2;;
    --fix-mode) FIX_MODE="$2"; shift 2;;
    --fix-cmd) FIX_CMD="$2"; shift 2;;
    --max-fix) MAX_FIX_ATTEMPTS="$2"; shift 2;;
    --any-fail) ANY_FAIL="$2"; shift 2;;
    --auto-conflict) AUTO_CONFLICT="$2"; shift 2;;
    --merge) MERGE_MODE="$2"; shift 2;;
    --merge-wait-sec) MERGE_WAIT_SEC="$2"; shift 2;;
    --allow-direct-merge) ALLOW_DIRECT_MERGE="1"; shift 1;;
    --force-merge) FORCE_MERGE="1"; shift 1;;
    --delete-branch) DELETE_BRANCH="1"; shift 1;;
    --deploy) DEPLOY_MODE="$2"; shift 2;;
    --deploy-env) DEPLOY_ENV="$2"; shift 2;;
    --deploy-trigger-wait-sec) DEPLOY_TRIGGER_WAIT_SEC="$2"; shift 2;;
    --deploy-wait-max-sec) DEPLOY_WAIT_MAX_SEC="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "${REPO_ROOT}" ]] || die "not a git repo"
cd "${REPO_ROOT}"

require_cmd git
require_cmd python3
require_cmd gh

if [[ -z "${REPO}" ]]; then
  REPO="$(detect_repo_from_origin || true)"
fi
[[ -n "${REPO}" ]] || die "cannot detect repo; pass --repo owner/repo"

if [[ -z "${HEAD_BRANCH}" ]]; then
  HEAD_BRANCH="$(git branch --show-current)"
fi
[[ -n "${HEAD_BRANCH}" ]] || die "cannot detect head branch; pass --head"

if [[ "${HEAD_BRANCH}" == "${BASE_BRANCH}" ]]; then
  die "head branch equals base branch (${BASE_BRANCH}); refusing."
fi

gh_ensure_auth
git_setup_push_auth_best_effort

# Respect PR bot merge policy by default (unless --force-merge).
MERGE_POLICY="$(merge_policy_for_branch "${HEAD_BRANCH}")"
echo "[local-e2e] merge_policy=${MERGE_POLICY} (branch=${HEAD_BRANCH})"
if [[ "${MERGE_POLICY}" != "bot_squash" && "${FORCE_MERGE}" != "1" ]]; then
  echo "[local-e2e] merge disabled by policy (merge_policy=${MERGE_POLICY}). Use --force-merge to override."
  MERGE_MODE="skip"
fi

# Ensure PR
if [[ -z "${PR_NUMBER}" ]]; then
  PR_NUMBER="$(pr_find_open_for_head "${REPO}" "${HEAD_BRANCH}")"
fi
if [[ -z "${PR_NUMBER}" ]]; then
  echo "[local-e2e] no open PR for head=${HEAD_BRANCH}; creating..."
  bash scripts/require_local_gate.sh --auto-run --caller local-merge-deploy-orchestrator
  pr_create "${REPO}" "${BASE_BRANCH}" "${HEAD_BRANCH}" "${HEAD_BRANCH}" "${PR_BODY_FILE:-}"
  PR_NUMBER="$(pr_find_open_for_head "${REPO}" "${HEAD_BRANCH}")"
fi
[[ -n "${PR_NUMBER}" ]] || die "cannot find or create PR for branch=${HEAD_BRANCH}"

echo "[local-e2e] repo=${REPO} pr=#${PR_NUMBER} base=${BASE_BRANCH} head=${HEAD_BRANCH}"

# Best-effort label to keep merge-bot eligible on bot_squash branches
if [[ "${MERGE_MODE}" != "skip" ]]; then
  gh pr edit "${PR_NUMBER}" --repo "${REPO}" --add-label "pr-bot/ready-to-merge" >/dev/null 2>&1 || true
fi

# Fix loop (local)
export AUTOPILOT_ANY_FAIL="${ANY_FAIL}"
export AUTOPILOT_AUTO_CONFLICT="${AUTO_CONFLICT}"

if [[ "${FIX_MODE}" == "auto" ]]; then
  if [[ -z "${FIX_CMD}" ]]; then
    die "fix-mode=auto requires --fix-cmd or AUTOPILOT_FIX_CMD"
  fi
  export AUTOPILOT_FIX_CMD="${FIX_CMD}"
else
  unset AUTOPILOT_FIX_CMD || true
fi

set +e
bash scripts/autopilot_local.sh --repo "${REPO}" --pr "${PR_NUMBER}" --max "${MAX_FIX_ATTEMPTS}" --out "${OUT_DIR}"
AP_RC=$?
set -e

if [[ $AP_RC -ne 0 ]]; then
  # autopilot_local already produced evidence under OUT_DIR/pr-<n>/FAILURE.md
  if [[ $AP_RC -eq 3 ]]; then
    echo "[local-e2e] STOP: needs manual fix. See: ${OUT_DIR}/pr-${PR_NUMBER}/FAILURE.md"
  else
    echo "[local-e2e] STOP: autopilot_local exited rc=${AP_RC}. See: ${OUT_DIR}/pr-${PR_NUMBER}/FAILURE.md"
  fi
  exit "$AP_RC"
fi

# Merge
if [[ "${MERGE_MODE}" != "skip" ]]; then
  if [[ "${MERGE_MODE}" == "direct" && "${ALLOW_DIRECT_MERGE}" != "1" ]]; then
    die "merge=direct requested but ALLOW_DIRECT_MERGE!=1. Re-run with --allow-direct-merge (or export ALLOW_DIRECT_MERGE=1)."
  fi

  if [[ "${MERGE_MODE}" == "auto" ]]; then
    echo "[local-e2e] merge: waiting ${MERGE_WAIT_SEC}s for merge-bot..."
    merged_by_bot="0"
    if wait_for_pr_merged "${REPO}" "${PR_NUMBER}" "${MERGE_WAIT_SEC}" >/dev/null 2>&1; then
      echo "[local-e2e] merge: merged by bot"
      merged_by_bot="1"
    else
      if [[ "${MERGE_BOT_DISPATCH}" == "1" ]]; then
        echo "[local-e2e] merge: bot not merged (or slow) -> dispatching merge-bot workflow (break-glass confirm=${MERGE_BOT_DISPATCH_CONFIRM})"
        if dispatch_merge_bot "${REPO}" "${PR_NUMBER}" "${MERGE_BOT_DISPATCH_REF}" >/dev/null 2>&1; then
          echo "[local-e2e] merge: dispatched; waiting ${MERGE_BOT_DISPATCH_WAIT_SEC}s for merge result..."
          if wait_for_pr_merged "${REPO}" "${PR_NUMBER}" "${MERGE_BOT_DISPATCH_WAIT_SEC}" >/dev/null 2>&1; then
            echo "[local-e2e] merge: merged by bot (dispatch)"
            merged_by_bot="1"
          else
            echo "[local-e2e] merge: dispatch did not merge within ${MERGE_BOT_DISPATCH_WAIT_SEC}s"
          fi
        else
          echo "[local-e2e] merge: dispatch failed (no token logged)."
        fi
      fi
      if [[ "${merged_by_bot}" != "1" ]]; then
        if [[ "${ALLOW_DIRECT_MERGE}" == "1" ]]; then
          echo "[local-e2e] merge: bot not merged (or slow) -> direct merge (explicitly allowed)"
          MERGE_MODE="direct"
        else
          echo "[local-e2e] merge: bot not merged (or slow). Direct merge is disabled by default."
          echo "[local-e2e] merge: re-run with --merge-wait-sec <N> to wait longer, or --allow-direct-merge to allow fallback."
          exit 9
        fi
      fi
    fi
  fi

  if [[ "${MERGE_MODE}" == "direct" ]]; then
    meta="$(pr_get_meta "${REPO}" "${PR_NUMBER}")"
    if [[ "$(printf '%s' "${meta}" | pr_is_merged)" == "1" ]]; then
      echo "[local-e2e] merge: already merged"
    else
      mergeable_state="$(printf '%s' "${meta}" | pr_mergeable_state)"
      if [[ "${mergeable_state}" == "behind" ]]; then
        echo "[local-e2e] mergeable_state=behind -> update branch from ${BASE_BRANCH} and re-run."
        echo "[local-e2e] suggested:"
        echo "  git fetch origin && git merge origin/${BASE_BRANCH} && git push"
        exit 8
      fi

      echo "[local-e2e] merge: gh pr merge --squash"
      if [[ "${DELETE_BRANCH}" == "1" ]]; then
        gh pr merge "${PR_NUMBER}" --repo "${REPO}" --squash --delete-branch
      else
        gh pr merge "${PR_NUMBER}" --repo "${REPO}" --squash
      fi
    fi
  fi
else
  echo "[local-e2e] merge: skip"
fi

# Wait for merge_commit_sha (needed for deploy watch)
meta="$(wait_for_pr_merged "${REPO}" "${PR_NUMBER}" 120 || true)"
if [[ -z "${meta}" ]]; then
  echo "[local-e2e] deploy: PR not merged; skipping deploy watch."
  exit 0
fi

MERGE_SHA="$(printf '%s' "${meta}" | pr_merge_commit_sha)"
if [[ -z "${MERGE_SHA}" ]]; then
  echo "[local-e2e] deploy: merge_commit_sha missing; skipping deploy watch."
  exit 0
fi

if [[ "${DEPLOY_MODE}" == "skip" ]]; then
  echo "[local-e2e] deploy: skip"
  exit 0
fi

FLAGS="$(changed_flags_for_head)"
WEB_EXPECTED="$(printf '%s' "${FLAGS}" | python3 -c 'import sys; print("1" if "web=1" in sys.stdin.read() else "0")')"
BACKEND_EXPECTED="$(printf '%s' "${FLAGS}" | python3 -c 'import sys; print("1" if "backend=1" in sys.stdin.read() else "0")')"

echo "[local-e2e] deploy: merge_sha=${MERGE_SHA:0:7} web_expected=${WEB_EXPECTED} backend_expected=${BACKEND_EXPECTED}"

if [[ "${WEB_EXPECTED}" != "1" && "${BACKEND_EXPECTED}" != "1" ]]; then
  echo "[local-e2e] deploy: no web/backend changes detected; skipping deploy."
  exit 0
fi

wait_or_dispatch_named_run() {
  local wf_name="$1"     # run.name (e.g. deploy-web)
  local wf_file="$2"     # workflow file for dispatch (e.g. deploy-web.yml)
  local max_wait_sec="$3"

  local start
  start="$(date +%s)"
  local rid=""
  if [[ "${DEPLOY_MODE}" == "dispatch" ]]; then
    max_wait_sec=0
  fi

  while true; do
    rid="$(find_run_id_by_name_and_sha "${REPO}" "${MERGE_SHA}" "${wf_name}")"
    if [[ -n "${rid}" ]]; then
      echo "${rid}"
      return 0
    fi
    local now
    now="$(date +%s)"
    if (( now - start >= max_wait_sec )); then
      break
    fi
    sleep 5
  done

  # Not found: dispatch fallback (only in auto/dispatch)
  if [[ "${DEPLOY_MODE}" == "auto" || "${DEPLOY_MODE}" == "dispatch" ]]; then
    echo "[local-e2e] deploy: run not found for ${wf_name}; dispatching ${wf_file}"
    gh workflow run "${wf_file}" --repo "${REPO}" --ref "${BASE_BRANCH}" -f env="${DEPLOY_ENV}" >/dev/null || true
    local retry_start
    retry_start="$(date +%s)"
    while true; do
      rid="$(find_run_id_by_name_and_sha "${REPO}" "${MERGE_SHA}" "${wf_name}")"
      if [[ -n "${rid}" ]]; then
        echo "${rid}"
        return 0
      fi
      local now2
      now2="$(date +%s)"
      if (( now2 - retry_start >= DEPLOY_TRIGGER_WAIT_SEC )); then
        break
      fi
      sleep 5
    done
  fi

  echo ""
  return 1
}

watch_one_run() {
  local name="$1"
  local run_id="$2"

  echo "[local-e2e] deploy: waiting run ${name} id=${run_id}..."
  run_json="$(wait_run_completed "${REPO}" "${run_id}" "${DEPLOY_WAIT_MAX_SEC}" || true)"
  if [[ -z "${run_json}" ]]; then
    echo "[local-e2e] deploy: timeout waiting ${name} (id=${run_id})"
    return 1
  fi

  url="$(printf '%s' "${run_json}" | run_html_url)"
  conc="$(printf '%s' "${run_json}" | run_conclusion)"
  ok="$(printf '%s' "${run_json}" | run_conclusion_ok)"
  echo "[local-e2e] deploy: ${name} conclusion=${conc} url=${url}"

  bash scripts/ops/gh_pull_run_logs.sh --repo "${REPO}" --run-id "${run_id}" --out "${OUT_DIR}" >/dev/null 2>&1 || true

  [[ "${ok}" == "1" ]]
}

# deploy-web / deploy-backend
deploy_failed="0"
if [[ "${WEB_EXPECTED}" == "1" ]]; then
  rid="$(wait_or_dispatch_named_run "deploy-web" "deploy-web.yml" "${DEPLOY_TRIGGER_WAIT_SEC}")"
  if [[ -n "${rid}" ]]; then
    if ! watch_one_run "deploy-web" "${rid}"; then
      deploy_failed="1"
    fi
  else
    echo "[local-e2e] deploy-web: not found (skipping)"
  fi
fi

if [[ "${BACKEND_EXPECTED}" == "1" ]]; then
  rid="$(wait_or_dispatch_named_run "deploy-backend" "deploy-backend.yml" "${DEPLOY_TRIGGER_WAIT_SEC}")"
  if [[ -n "${rid}" ]]; then
    if ! watch_one_run "deploy-backend" "${rid}"; then
      deploy_failed="1"
    fi
  else
    echo "[local-e2e] deploy-backend: not found (skipping)"
  fi
fi

if [[ "${deploy_failed}" == "1" ]]; then
  echo "[local-e2e] deploy: one or more deploy workflows failed; pulling chain logs..."
  bash scripts/ops/ci_pull_deploy_chain_logs.sh --repo "${REPO}" --sha "${MERGE_SHA}" --out "${OUT_DIR}" >/dev/null 2>&1 || true
  exit 20
fi

# post-deploy-validate (workflow_run)
wait_named_run_only() {
  local wf_name="$1"
  local max_wait_sec="$2"
  local start
  start="$(date +%s)"
  local rid=""

  while true; do
    rid="$(find_run_id_by_name_and_sha "${REPO}" "${MERGE_SHA}" "${wf_name}")"
    if [[ -n "${rid}" ]]; then
      echo "${rid}"
      return 0
    fi
    local now
    now="$(date +%s)"
    if (( now - start >= max_wait_sec )); then
      break
    fi
    sleep 10
  done

  echo ""
  return 1
}

rid="$(wait_named_run_only "post-deploy-validate" "${DEPLOY_WAIT_MAX_SEC}" || true)"
if [[ -n "${rid}" ]]; then
  if ! watch_one_run "post-deploy-validate" "${rid}"; then
    echo "[local-e2e] validate failed; watching rollback (if enabled)..."
    rb_rid="$(wait_named_run_only "rollback" "${DEPLOY_WAIT_MAX_SEC}" || true)"
    if [[ -n "${rb_rid}" ]]; then
      watch_one_run "rollback" "${rb_rid}" || true
    else
      echo "[local-e2e] rollback run not found."
    fi
  fi
else
  echo "[local-e2e] post-deploy-validate: not found (maybe DEPLOY_ENABLED!=true or workflows skipped)."
fi

bash scripts/ops/ci_pull_deploy_chain_logs.sh --repo "${REPO}" --sha "${MERGE_SHA}" --out "${OUT_DIR}" >/dev/null 2>&1 || true
echo "[local-e2e] deploy: pulled best-effort logs. See: ${OUT_DIR}/main-${MERGE_SHA:0:7}/DEPLOY-CHAIN.md"
echo "[local-e2e] done."
