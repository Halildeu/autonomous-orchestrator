#!/usr/bin/env bash
set -euo pipefail

# Prevent accidental secret leakage if the caller enabled xtrace.
set +x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LIGHT_MODE=0

# Parse --light flag (must come before positional args)
for arg in "$@"; do
  case "${arg}" in
    --light) LIGHT_MODE=1;;
  esac
done

LOG_DIR="${LOCAL_GATE_LOG_DIR:-${ROOT_DIR}/.cache/reports/local-gate-chain}"
STATUS_PATH="${LOG_DIR}/status.json"
RESULTS_TSV="${LOG_DIR}/results.tsv"

mkdir -p "${LOG_DIR}/logs"

declare -a STEP_RESULTS=()
OVERALL_STATUS="RUNNING"
RUN_STARTED_AT_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
LOCAL_GATE_DEPENDENCY_SCAN_MODE="${LOCAL_GATE_DEPENDENCY_SCAN_MODE:-cache-only}"
LOCAL_GATE_DEPENDENCY_SCAN_ALLOW_BOOTSTRAP_ON_CACHE_MISS="${LOCAL_GATE_DEPENDENCY_SCAN_ALLOW_BOOTSTRAP_ON_CACHE_MISS:-true}"

if [[ -f "${SCRIPT_DIR}/ops/load_local_env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/ops/load_local_env.sh"
fi

# NVM support: add Node 22 to PATH if managed via NVM (git hooks don't inherit login shell)
if ! command -v node >/dev/null 2>&1 || [[ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)" != "22" ]]; then
  _nvm_dir="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "${_nvm_dir}/nvm.sh" ]]; then
    _nvm_node22="$(NVM_DIR="${_nvm_dir}" bash -c 'source "$NVM_DIR/nvm.sh" --no-use 2>/dev/null; nvm which 22 2>/dev/null' || true)"
    if [[ -x "${_nvm_node22}" ]]; then
      export PATH="$(dirname "${_nvm_node22}"):${PATH}"
    fi
    unset _nvm_node22
  fi
  unset _nvm_dir
fi

info() {
  printf '[local-gate] %s\n' "$*"
}

sanitize_name() {
  printf '%s' "$1" | tr ' /:' '---'
}

compute_worktree_fingerprint() {
  python3 "${SCRIPT_DIR}/ops/compute_worktree_fingerprint.py" --repo-root "${ROOT_DIR}"
}

node22_prefix() {
  if command -v volta >/dev/null 2>&1; then
    printf 'volta run --node 22'
    return 0
  fi

  if command -v node >/dev/null 2>&1; then
    local major
    major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
    if [[ "${major}" == "22" ]]; then
      printf ''
      return 0
    fi
  fi

  if [[ -x /opt/homebrew/opt/node@22/bin/node ]]; then
    printf 'env PATH=/opt/homebrew/opt/node@22/bin:%s' "${PATH}"
    return 0
  fi

  return 1
}

run_with_log() {
  local step="$1"
  shift

  local safe_name log_path step_timeout
  safe_name="$(sanitize_name "${step}")"
  log_path="${LOG_DIR}/logs/${safe_name}.log"
  step_timeout="${LOCAL_GATE_STEP_TIMEOUT:-600}"  # default 10 minutes per step

  info "START ${step}"

  local child_pid rc=0
  (
    cd "${ROOT_DIR}"
    "$@"
  ) >"${log_path}" 2>&1 &
  child_pid=$!

  # Wait with timeout — kill if exceeds step_timeout
  local waited=0
  while kill -0 "${child_pid}" 2>/dev/null; do
    if [[ "${waited}" -ge "${step_timeout}" ]]; then
      kill -TERM "${child_pid}" 2>/dev/null
      sleep 2
      kill -KILL "${child_pid}" 2>/dev/null || true
      wait "${child_pid}" 2>/dev/null || true
      info "TIMEOUT ${step} (${step_timeout}s exceeded)"
      STEP_RESULTS+=("TIMEOUT|${step}|${log_path}")
      printf 'TIMEOUT(%s)\t%s\t%s\n' "${step_timeout}" "${step}" "${log_path}" >>"${RESULTS_TSV}"
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done

  wait "${child_pid}" 2>/dev/null
  rc=$?

  if [[ "${rc}" -eq 0 ]]; then
    info "PASS  ${step}"
    STEP_RESULTS+=("PASS|${step}|${log_path}")
    printf 'PASS\t%s\t%s\n' "${step}" "${log_path}" >>"${RESULTS_TSV}"
  else
    info "FAIL  ${step} (log: ${log_path})"
    STEP_RESULTS+=("FAIL(${rc})|${step}|${log_path}")
    printf 'FAIL(%s)\t%s\t%s\n' "${rc}" "${step}" "${log_path}" >>"${RESULTS_TSV}"
    return "${rc}"
  fi
}

run_shell_step() {
  local step="$1"
  shift
  run_with_log "${step}" /bin/zsh -lc "$*"
}

NODE22_CMD="$(node22_prefix || true)"
if [[ -z "${NODE22_CMD}" ]]; then
  if command -v node >/dev/null 2>&1; then
    current_node_major="$(node -e 'process.stdout.write(process.versions.node.split(".")[0])' 2>/dev/null || true)"
  else
    current_node_major=""
  fi
else
  current_node_major=""
fi

if [[ -z "${NODE22_CMD}" && "${current_node_major}" != "22" ]]; then
  info "FAIL toolchain: Node 22 bulunamadı. Volta veya node@22 yükleyin."
  exit 2
fi

write_status_artifacts() {
  local exit_code="$1"
  local finished_at branch head_sha fingerprint summary_path
  finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  branch="$(git branch --show-current)"
  head_sha="$(git rev-parse HEAD)"
  fingerprint="$(compute_worktree_fingerprint)"
  summary_path="${LOG_DIR}/summary.txt"

  if [[ "${exit_code}" -eq 0 ]]; then
    OVERALL_STATUS="PASS"
  else
    OVERALL_STATUS="FAIL"
  fi

  {
    printf 'local gate summary\n'
    printf 'repo=%s\n' "${ROOT_DIR}"
    printf 'branch=%s\n' "${branch}"
    printf 'head_sha=%s\n' "${head_sha}"
    printf 'worktree_fingerprint=%s\n' "${fingerprint}"
    printf 'started_at_utc=%s\n' "${RUN_STARTED_AT_UTC}"
    printf 'finished_at_utc=%s\n' "${finished_at}"
    printf 'overall_status=%s\n' "${OVERALL_STATUS}"
    printf 'nvd_api_key_loaded=%s\n' "$([[ -n "${NVD_API_KEY:-}" ]] && printf yes || printf no)"
    printf 'dependency_scan_mode=%s\n' "${LOCAL_GATE_DEPENDENCY_SCAN_MODE}"
    printf 'gitleaks_mode=%s\n' "$([[ -n "${secrets_range:-}" ]] && printf git-range || printf full-detect)"
    for row in "${STEP_RESULTS[@]+"${STEP_RESULTS[@]}"}"; do
      IFS='|' read -r status step log_path <<<"${row}"
      printf '%s\t%s\t%s\n' "${status}" "${step}" "${log_path}"
    done
  } >"${summary_path}"

  python3 - "${RESULTS_TSV}" "${STATUS_PATH}" "${ROOT_DIR}" "${branch}" "${head_sha}" "${fingerprint}" "${RUN_STARTED_AT_UTC}" "${finished_at}" "${OVERALL_STATUS}" "${summary_path}" <<'PY'
import json
import sys
from pathlib import Path

results_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
repo = sys.argv[3]
branch = sys.argv[4]
head_sha = sys.argv[5]
fingerprint = sys.argv[6]
started_at = sys.argv[7]
finished_at = sys.argv[8]
overall_status = sys.argv[9]
summary_path = sys.argv[10]

steps = []
if results_path.exists():
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        status, step, log_path = line.split("\t", 2)
        steps.append({"status": status, "step": step, "log_path": log_path})

payload = {
    "repo": repo,
    "branch": branch,
    "head_sha": head_sha,
    "worktree_fingerprint": fingerprint,
    "started_at_utc": started_at,
    "finished_at_utc": finished_at,
    "overall_status": overall_status,
    "summary_path": summary_path,
    "steps": steps,
}
status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

finalize_run() {
  local exit_code=$?
  write_status_artifacts "${exit_code}"
  if [[ "${exit_code}" -eq 0 ]]; then
    info "Tamamlandı. Özet: ${LOG_DIR}/summary.txt"
  else
    info "Fail. Özet: ${LOG_DIR}/summary.txt"
  fi
  exit "${exit_code}"
}

: >"${RESULTS_TSV}"
trap finalize_run EXIT

detect_gitleaks_range() {
  if [[ -n "${GITLEAKS_LOG_OPTS:-}" ]]; then
    printf '%s' "${GITLEAKS_LOG_OPTS}"
    return 0
  fi

  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    local merge_base
    merge_base="$(git merge-base origin/main HEAD)"
    printf '%s..HEAD' "${merge_base}"
    return 0
  fi

  if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    printf 'HEAD~1..HEAD'
    return 0
  fi

  printf ''
}

docs_gate_cmd='
set -euo pipefail
python3 scripts/ci/check_doc_zone_purity.py
python3 scripts/docflow_next.py render-flow --check
python3 scripts/check_doc_templates.py
python3 scripts/check_doc_ids.py
python3 scripts/check_unique_delivery_ids.py
python3 scripts/check_id_registry.py
python3 scripts/check_doc_locations.py
python3 scripts/check_acceptance_evidence.py
python3 scripts/check_story_links.py
python3 scripts/check_story_downstream_optional.py
python3 scripts/check_spec_refs.py
python3 scripts/check_doc_routing_strict.py
python3 scripts/check_bm_bench_pack_integrity.py
python3 scripts/check_bm_content_policy.py
python3 scripts/check_bench_content_policy.py
python3 scripts/check_trace_content_policy.py
python3 scripts/check_prd_content_policy.py
python3 scripts/check_prd_delivery_items.py
python3 scripts/check_spec_content_policy.py
python3 scripts/check_runbook_required_sections.py
python3 scripts/check_doc_template_map_policy.py
python3 scripts/check_doc_heading_contract.py
python3 scripts/check_template_control_coverage.py
python3 scripts/check_doc_template_strictness.py
python3 scripts/check_tp_risk_policy.py
python3 scripts/check_guides_policy.py
python3 scripts/check_guides_prefix.py
python3 scripts/check_nonprefix_naming_policy.py
python3 scripts/check_doc_folder_file_naming.py
python3 scripts/check_doc_cross_mix_report.py
python3 scripts/check_doc_content_boundary_policy.py
python3 scripts/check_doc_content_boundaries.py
python3 scripts/check_doc_repair_reason_map.py
python3 scripts/check_doc_repair_autopr_policy.py
python3 scripts/check_doc_chain.py
python3 scripts/check_transition_authority_map.py
python3 scripts/report_transition_reference_consumers.py --repo-root . --out-json .cache/reports/transition_reference_consumers.v1.json --out-md .cache/reports/transition_reference_consumers.v1.md
python3 scripts/check_governance_migration.py
python3 scripts/check_trace_quality_policy.py
python3 scripts/check_trace_quality.py
python3 scripts/check_prd_complexity.py
python3 scripts/check_doc_maturity_rubric.py --flow-path docs/03-delivery/PROJECT-FLOW.tsv
python3 scripts/check_local_orchestrator_guardrails.py
python3 scripts/check_robots_policy.py
python3 scripts/check_robots_drift.py
python3 scripts/check_robots_tbd_coverage.py
python3 scripts/check_auth_registry.py
python3 scripts/check_workflow_model_ssot.py
'

if [[ -n "${NODE22_CMD}" ]]; then
  web_gate_cmd="
set -euo pipefail
${NODE22_CMD} python3 scripts/check_version_gates.py --mode ci
${NODE22_CMD} pnpm -C web install --frozen-lockfile
${NODE22_CMD} pnpm -C web exec playwright install chromium
${NODE22_CMD} pnpm -C web run tokens:build -- --check
python3 scripts/check_theme_contract_consistency.py
python3 scripts/check_tailwind_token_map.py
python3 scripts/check_theme_override_allowlist.py
python3 scripts/check_no_hardcoded_theme_styles.py
${NODE22_CMD} bash scripts/run_lint_web.sh
${NODE22_CMD} bash scripts/run_tests_web.sh
${NODE22_CMD} bash scripts/run_tests_web.sh pw-preauth
"
else
  web_gate_cmd='
set -euo pipefail
python3 scripts/check_version_gates.py --mode ci
pnpm -C web install --frozen-lockfile
pnpm -C web exec playwright install chromium
pnpm -C web run tokens:build -- --check
python3 scripts/check_theme_contract_consistency.py
python3 scripts/check_tailwind_token_map.py
python3 scripts/check_theme_override_allowlist.py
python3 scripts/check_no_hardcoded_theme_styles.py
bash scripts/run_lint_web.sh
bash scripts/run_tests_web.sh
bash scripts/run_tests_web.sh pw-preauth
'
fi

module_delivery_cmd='
set -euo pipefail
python3 ci/check_module_delivery_lanes.py --strict
python3 extensions/PRJ-PM-SUITE/contract/check_feature_execution_contract.py --repo-root . --base HEAD~1 --head HEAD --out .cache/reports/feature_execution_contract_module_delivery.v1.json
python3 extensions/PRJ-PM-SUITE/contract/build_delivery_session_packet.py --repo-root . --out .cache/reports/delivery_session_packet_module_delivery.v1.json
python3 extensions/PRJ-PM-SUITE/contract/check_delivery_session_guard.py --repo-root . --packet .cache/reports/delivery_session_packet_module_delivery.v1.json --base HEAD~1 --head HEAD --out .cache/reports/delivery_session_guard_module_delivery.v1.json
python3 extensions/PRJ-UX-NORTH-STAR/contract/check_ux_catalog_enforcement.py --repo-root . --base HEAD~1 --head HEAD --out .cache/reports/ux_catalog_enforcement_module_delivery.v1.json
python3 ci/run_module_delivery_lane.py --lane unit
python3 ci/run_module_delivery_lane.py --lane database
python3 ci/run_module_delivery_lane.py --lane api
python3 ci/run_module_delivery_lane.py --lane contract
python3 ci/run_module_delivery_lane.py --lane integration
python3 ci/run_module_delivery_lane.py --lane e2e
'

security_cmd='
set -euo pipefail
python3 scripts/check_security_all.py
python3 scripts/check_live_release_provisioning_contract.py
bash backend/scripts/ci/security/run-sast.sh
DEPENDENCY_CHECK_MODE='"${LOCAL_GATE_DEPENDENCY_SCAN_MODE}"' DEPENDENCY_CHECK_ALLOW_BOOTSTRAP_ON_CACHE_MISS='"${LOCAL_GATE_DEPENDENCY_SCAN_ALLOW_BOOTSTRAP_ON_CACHE_MISS}"' bash backend/scripts/ci/security/run-dependency-scan.sh
bash backend/scripts/ci/security/generate-sbom-and-sign.sh
ruby backend/scripts/ci/security/export-flag-health.rb
python3 scripts/check_security_remediation_contract.py
if [[ -n "${ZAP_TARGET_URL:-}" ]]; then
  bash backend/scripts/ci/security/run-dast.sh
else
  printf "[local-gate] ZAP_TARGET_URL yok; DAST skip\n"
fi
'

secrets_range="$(detect_gitleaks_range)"
if [[ -n "${secrets_range}" ]]; then
  secrets_cmd="
set -euo pipefail
gitleaks git --no-banner --redact --log-opts='${secrets_range}'
"
else
  secrets_cmd='
set -euo pipefail
gitleaks detect --source . --no-banner --redact
'
fi

if [[ "${LIGHT_MODE}" == "1" ]]; then
  # === LIGHT MODE (worktree) ===
  # Policy: secrets + schema-policy-enforcement + scope-aware lint
  info "LIGHT MODE aktif (worktree)"

  run_shell_step "secrets-gate" "${secrets_cmd}"

  run_shell_step "schema-policy-enforcement" '
set -euo pipefail
python3 ci/validate_schemas.py
python3 ci/check_standards_lock.py
'

  # Scope-aware lint: check staged files, run lint only for changed scopes
  staged_files="$(git diff --cached --name-only 2>/dev/null || true)"

  has_backend=0
  has_web=0
  if echo "${staged_files}" | grep -q '^backend/'; then
    has_backend=1
  fi
  if echo "${staged_files}" | grep -q '^web/'; then
    has_web=1
  fi

  if [[ "${has_backend}" == "1" ]]; then
    if [[ -x backend/mvnw ]] && command -v java >/dev/null 2>&1; then
      run_shell_step "backend-lint" '
set -euo pipefail
cd backend
./mvnw -q -DskipTests compile
'
    else
      info "WARN: backend/ degisti ama Java/Maven bulunamadi; backend-lint skip."
    fi
  fi

  if [[ "${has_web}" == "1" ]]; then
    if command -v node >/dev/null 2>&1 && command -v pnpm >/dev/null 2>&1; then
      if [[ -n "${NODE22_CMD}" ]]; then
        run_shell_step "web-lint" "
set -euo pipefail
${NODE22_CMD} bash scripts/run_lint_web.sh
"
      else
        run_shell_step "web-lint" '
set -euo pipefail
bash scripts/run_lint_web.sh
'
      fi
    else
      info "WARN: web/ degisti ama Node/pnpm bulunamadi; web-lint skip."
    fi
  fi

else
  # === FULL MODE (canonical tree) ===
  run_shell_step "docs-gate" "${docs_gate_cmd}"
  run_shell_step "layout-gate" '
set -euo pipefail
python3 scripts/check_backend_service_layout.py
python3 scripts/check_web_mfe_layout.py
'
  run_shell_step "schema-policy-enforcement" '
set -euo pipefail
python3 ci/validate_schemas.py
python3 ci/policy_dry_run.py --fixtures fixtures/envelopes --out .cache/reports/policy_dry_run_local.json
python3 ci/check_standards_lock.py
python3 extensions/PRJ-WORK-INTAKE/check_policy_work_intake_modularization.py
python3 extensions/PRJ-OBSERVABILITY-OTEL/coverage_visibility_report.py --repo-root . --out-json .cache/reports/coverage_visibility.v1.json --out-md .cache/reports/coverage_visibility.v1.md
python3 extensions/PRJ-OBSERVABILITY-OTEL/export_observability_coverage_matrix.py --repo-root . --out-json .cache/reports/observability_coverage_matrix.v1.json --out-md .cache/reports/observability_coverage_matrix.v1.md
python3 scripts/check_branch_protection_solo_policy.py --mode warn --out .cache/reports/branch_protection_solo_policy_ci.v1.json
python3 -c "import src.ops.manage" 2>/dev/null && python3 -m src.ops.manage enforcement-check --profile strict --baseline git:HEAD~1 --outdir .cache/reports/enforcement-check-local || echo "[skip] src.ops.manage not available in this repo"
'
  run_shell_step "web-gate" "${web_gate_cmd}"
  run_shell_step "backend-gate" '
set -euo pipefail
cd backend
./mvnw -DskipITs=true test
'
  run_shell_step "module-delivery" "${module_delivery_cmd}"
  run_shell_step "security-guardrails" "${security_cmd}"
  run_shell_step "secrets-gate" "${secrets_cmd}"
fi
