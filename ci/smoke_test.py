import json
import os
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path
from shutil import copytree, rmtree
import tomllib
from ci.smoke_helpers.smoke_cli_checks import run_cli_contract_checks


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def is_git_work_tree(repo_root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False

    return proc.returncode == 0 and proc.stdout.strip() == "true"


def is_git_clean_work_tree(repo_root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False

    return proc.returncode == 0 and not (proc.stdout or "").strip()


def assert_not_git_ignored(repo_root: Path, rel_path: str) -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-v", rel_path],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode not in (0, 1):
        raise SystemExit(
            "Smoke test failed: git check-ignore errored for "
            + rel_path
            + ":\n"
            + (proc.stderr or "").strip()
        )
    output = (proc.stdout or "").strip()
    if output:
        raise SystemExit(f"Smoke test failed: {rel_path} is ignored by git:\n{output}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    quota_policy_path = repo_root / "policies" / "policy_quota.v1.json"
    quota_policy_repo: str | None = None
    quota_policy_overridden = False
    if quota_policy_path.exists():
        quota_policy_repo = quota_policy_path.read_text(encoding="utf-8")
        relaxed_quota_policy = {
            "version": "v1",
            "default": {"max_runs_per_day": 1000, "max_est_tokens_per_day": 10000000},
            "overrides": {"TENANT-LOCAL": {"max_runs_per_day": 1000, "max_est_tokens_per_day": 10000000}},
        }
        quota_policy_path.write_text(
            json.dumps(relaxed_quota_policy, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        quota_policy_overridden = True
        quota_store_path = repo_root / ".cache" / "tenant_quota_store.v1.json"
        if quota_store_path.exists():
            quota_store_path.unlink()

    run_cli_contract_checks(repo_root)

    # Repo hygiene guard: ensure critical JSON config files are NOT ignored.
    # (In CI, checkout is a git work tree; locally we skip if not in git.)
    in_git = is_git_work_tree(repo_root)
    if in_git:
        critical_paths = [
            "schemas/request-envelope.schema.json",
            "policies/policy_security.v1.json",
            "workflows/wf_core.v1.json",
            "fixtures/envelopes/0001.json",
            "orchestrator/strategy_table.v1.json",
        ]
        for rel_path in critical_paths:
            assert_not_git_ignored(repo_root, rel_path)
    else:
        print("NOTE: not in a git work tree; skipping gitignore guard.")

    run([sys.executable, str(repo_root / "ci" / "validate_schemas.py")])

    # Maintainability guardrail: Script Budget (soft=warn, hard=fail).
    report_path = repo_root / ".cache" / "script_budget" / "report.json"
    proc_budget = subprocess.run(
        [sys.executable, str(repo_root / "ci" / "check_script_budget.py"), "--out", str(report_path)],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_budget.returncode != 0:
        raise SystemExit(
            "Smoke test failed: script budget check must exit 0 (OK/WARN).\n"
            + (proc_budget.stderr or proc_budget.stdout or "")
        )
    if not report_path.exists():
        raise SystemExit("Smoke test failed: script budget report missing: " + str(report_path))
    try:
        budget_report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: failed to parse script budget report JSON.") from e

    budget_status = budget_report.get("status") if isinstance(budget_report, dict) else None
    if budget_status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: script budget status must be OK|WARN.")

    exceeded_hard = budget_report.get("exceeded_hard") if isinstance(budget_report, dict) else None
    function_hard = budget_report.get("function_hard") if isinstance(budget_report, dict) else None
    hard_exceeded = (len(exceeded_hard) if isinstance(exceeded_hard, list) else 0) + (
        len(function_hard) if isinstance(function_hard, list) else 0
    )
    if hard_exceeded != 0:
        raise SystemExit("Smoke test failed: script budget hard limit exceeded.")
    print(f"CRITICAL_SCRIPT_BUDGET status={budget_status} hard_exceeded={hard_exceeded}")

    # Side-effects SSOT manifest must exist and be valid JSON.
    se_manifest_path = repo_root / "docs" / "OPERATIONS" / "side-effects-manifest.v1.json"
    if not se_manifest_path.exists():
        raise SystemExit("Smoke test failed: missing side-effects manifest: docs/OPERATIONS/side-effects-manifest.v1.json")
    try:
        se_manifest = json.loads(se_manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: side-effects manifest must be valid JSON.") from e
    if not isinstance(se_manifest, dict):
        raise SystemExit("Smoke test failed: side-effects manifest must be a JSON object.")

    supported_now_raw = se_manifest.get("supported_now")
    blocked_now_raw = se_manifest.get("blocked_now")
    supported_now = (
        [x for x in supported_now_raw if isinstance(x, str) and x.strip()]
        if isinstance(supported_now_raw, list)
        else []
    )
    blocked_now = (
        [x for x in blocked_now_raw if isinstance(x, str) and x.strip()]
        if isinstance(blocked_now_raw, list)
        else []
    )
    print(f"CRITICAL_SIDE_EFFECT_MANIFEST: supported_now={supported_now} blocked_now={blocked_now}")

    run(
        [
            sys.executable,
            str(repo_root / "ci" / "policy_dry_run.py"),
            "--fixtures",
            str(repo_root / "fixtures" / "envelopes"),
            "--out",
            str(repo_root / "sim_report.json"),
        ]
    )

    sim_report = json.loads((repo_root / "sim_report.json").read_text(encoding="utf-8"))
    if "threshold_used" not in sim_report:
        raise SystemExit("Smoke test failed: sim_report.json missing threshold_used.")
    counts = sim_report.get("counts")
    if not isinstance(counts, dict):
        raise SystemExit("Smoke test failed: sim_report.json counts must be an object.")
    for k in ("allow", "suspend", "block_unknown_intent", "invalid_envelope"):
        if k not in counts:
            raise SystemExit(f"Smoke test failed: sim_report.json counts missing key: {k}")

    budget_warnings = sim_report.get("budget_warnings")
    if not isinstance(budget_warnings, dict):
        raise SystemExit("Smoke test failed: sim_report.json budget_warnings must be an object.")
    would_fail_tokens = budget_warnings.get("would_fail_budget_tokens")
    if not isinstance(would_fail_tokens, dict):
        raise SystemExit("Smoke test failed: sim_report.json budget_warnings.would_fail_budget_tokens must be an object.")
    if "count" not in would_fail_tokens or "examples" not in would_fail_tokens:
        raise SystemExit("Smoke test failed: budget_warnings.would_fail_budget_tokens missing count/examples.")

    if (repo_root / "fixtures" / "envelopes" / "0840_budget_tokens_exceeded.json").exists():
        if int(would_fail_tokens.get("count", 0)) < 1:
            raise SystemExit("Smoke test failed: expected budget_warnings would_fail_budget_tokens.count >= 1.")

    quota_warnings = sim_report.get("quota_warnings")
    if not isinstance(quota_warnings, dict):
        raise SystemExit("Smoke test failed: sim_report.json quota_warnings must be an object.")
    would_exceed_runs = quota_warnings.get("would_exceed_runs_per_day")
    if not isinstance(would_exceed_runs, dict):
        raise SystemExit("Smoke test failed: sim_report.json quota_warnings.would_exceed_runs_per_day must be an object.")
    if "count" not in would_exceed_runs or "examples" not in would_exceed_runs:
        raise SystemExit("Smoke test failed: quota_warnings.would_exceed_runs_per_day missing count/examples.")

    if (repo_root / "fixtures" / "envelopes" / "0999_invalid.json").exists():
        if int(counts.get("invalid_envelope", 0)) < 1:
            raise SystemExit("Smoke test failed: expected invalid_envelope >= 1 in sim_report.json")

    # Clean up legacy smoke outputs (older runs before evidence/** convention)
    for legacy in (
        repo_root / "evidence_smoke",
        repo_root / "evidence_smoke_invalid",
        repo_root / "evidence_smoke_suspend",
        repo_root / "evidence_smoke_suspend_write",
    ):
        if legacy.exists():
            rmtree(legacy)

    smoke_root = repo_root / "evidence" / "__smoke__"
    if smoke_root.exists():
        rmtree(smoke_root)

    out_dir_ok = smoke_root / "ok"

    out_file = repo_root / "fixtures" / "out.md"
    if out_file.exists():
        out_file.unlink()

    large_out_path = repo_root / "fixtures" / "large_out.md"
    if large_out_path.exists():
        large_out_path.unlink()

    idempotency_store_path = repo_root / ".cache" / "idempotency_store.v1.json"
    if idempotency_store_path.exists():
        idempotency_store_path.unlink()

    autonomy_store_path = repo_root / ".cache" / "autonomy_store.v1.json"
    if autonomy_store_path.exists():
        autonomy_store_path.unlink()

    governor_lock_path = repo_root / ".cache" / "governor_lock"
    if governor_lock_path.exists():
        governor_lock_path.unlink()

    proc1 = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0001.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_ok),
        ]
    )

    summary1 = json.loads(proc1.stdout)
    run_id = summary1.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise SystemExit("Smoke test failed: missing run_id in local_runner output.")

    if summary1.get("status") not in ("COMPLETED", "SUSPENDED"):
        raise SystemExit(f"Smoke test failed: unexpected status: {summary1.get('status')}")

    evidence_dir = out_dir_ok / run_id
    run_id_ok = run_id
    evidence_dir_ok = evidence_dir
    required_files = [
        evidence_dir / "request.json",
        evidence_dir / "summary.json",
        evidence_dir / "provenance.v1.json",
        evidence_dir / "integrity.manifest.v1.json",
        evidence_dir / "nodes" / "MOD_A" / "input.json",
        evidence_dir / "nodes" / "MOD_A" / "output.json",
        evidence_dir / "nodes" / "APPROVAL" / "input.json",
        evidence_dir / "nodes" / "APPROVAL" / "output.json",
        evidence_dir / "nodes" / "MOD_B" / "input.json",
        evidence_dir / "nodes" / "MOD_B" / "output.json",
    ]
    missing = [str(p) for p in required_files if not p.exists()]
    if missing:
        raise SystemExit("Smoke test failed: missing evidence files:\n" + "\n".join(missing))

    # Tool gateway smoke assertions: MOD_A must fs_read; MOD_B must declare fs_write.
    mod_a_out = json.loads((evidence_dir / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
    tool_calls_a = mod_a_out.get("tool_calls") if isinstance(mod_a_out, dict) else None
    if not (isinstance(tool_calls_a, list) and any(tc.get("tool") == "fs_read" for tc in tool_calls_a if isinstance(tc, dict))):
        raise SystemExit("Smoke test failed: MOD_A output must include tool_calls with fs_read.")

    mod_b_out = json.loads((evidence_dir / "nodes" / "MOD_B" / "output.json").read_text(encoding="utf-8"))
    tool_calls_b = mod_b_out.get("tool_calls") if isinstance(mod_b_out, dict) else None
    if not (isinstance(tool_calls_b, list) and any(tc.get("tool") == "fs_write" for tc in tool_calls_b if isinstance(tc, dict))):
        raise SystemExit("Smoke test failed: MOD_B output must include tool_calls with fs_write.")

    nodes = summary1.get("nodes", [])
    if isinstance(nodes, list):
        mod_b = next((n for n in nodes if isinstance(n, dict) and n.get("node_id") == "MOD_B"), None)
        if isinstance(mod_b, dict):
            out = mod_b.get("output", {})
            if isinstance(out, dict):
                side_effects = out.get("side_effects", {})
                if not (isinstance(side_effects, dict) and "would_write" in side_effects):
                    raise SystemExit(
                        "Smoke test failed: expected MOD_B to be dry-run (would_write missing)."
                    )

    if out_file.exists():
        raise SystemExit("Smoke test failed: dry_run must not create fixtures/out.md")

    if not idempotency_store_path.exists():
        raise SystemExit("Smoke test failed: idempotency store not created.")

    summary_path = evidence_dir / "summary.json"
    summary_file = json.loads(summary_path.read_text(encoding="utf-8"))
    required_summary_keys = [
        "run_id",
        "request_id",
        "tenant_id",
        "workflow_id",
        "result_state",
        "approval_threshold_used",
        "risk_score",
        "intent",
        "dry_run",
        "provider_used",
        "model_used",
        "secrets_used",
        "workflow_fingerprint",
        "started_at",
        "finished_at",
        "duration_ms",
        "idempotency_key_hash",
        "governor_mode_used",
        "governor_quarantine_hit",
        "governor_concurrency_limit_hit",
        "budget",
        "budget_usage",
        "budget_hit",
        "quota",
        "quota_usage_before",
        "quota_usage_after",
        "quota_hit",
        "autonomy_mode_used",
        "autonomy_store_snapshot",
        "autonomy_gate_triggered",
    ]
    missing_keys = [k for k in required_summary_keys if k not in summary_file]
    if missing_keys:
        raise SystemExit("Smoke test failed: missing summary keys:\n" + "\n".join(missing_keys))

    if summary_file.get("run_id") != run_id:
        raise SystemExit("Smoke test failed: summary.json run_id mismatch.")

    provenance_path = evidence_dir / "provenance.v1.json"
    prov = json.loads(provenance_path.read_text(encoding="utf-8"))
    if not isinstance(prov, dict):
        raise SystemExit("Smoke test failed: provenance.v1.json must be a JSON object.")
    if prov.get("version") != "v1":
        raise SystemExit("Smoke test failed: provenance.v1.json version must be v1.")
    if prov.get("run_id") != run_id:
        raise SystemExit("Smoke test failed: provenance.v1.json run_id mismatch.")
    if not isinstance(prov.get("created_at"), str) or not prov.get("created_at"):
        raise SystemExit("Smoke test failed: provenance.v1.json created_at must be a non-empty string.")

    git_info = prov.get("git")
    if not isinstance(git_info, dict) or "commit" not in git_info:
        raise SystemExit("Smoke test failed: provenance.v1.json git.commit missing.")
    commit = git_info.get("commit")
    if not isinstance(commit, str) or not commit:
        raise SystemExit("Smoke test failed: provenance.v1.json git.commit must be a non-empty string.")

    fingerprints = prov.get("fingerprints")
    if not isinstance(fingerprints, dict):
        raise SystemExit("Smoke test failed: provenance.v1.json fingerprints must be an object.")
    for k in ("workflow_fingerprint", "policies_hash", "registry_hash", "orchestrator_hash", "governor_hash"):
        if k not in fingerprints:
            raise SystemExit("Smoke test failed: provenance.v1.json fingerprints missing key: " + k)
    if fingerprints.get("workflow_fingerprint") != summary_file.get("workflow_fingerprint"):
        raise SystemExit("Smoke test failed: provenance workflow_fingerprint must match summary workflow_fingerprint.")

    for k in ("policies_hash", "registry_hash", "orchestrator_hash"):
        v = fingerprints.get(k)
        if not isinstance(v, str) or len(v) != 64:
            raise SystemExit("Smoke test failed: provenance fingerprint must be a sha256 hex string: " + k)

    governor_hash = fingerprints.get("governor_hash")
    if not isinstance(governor_hash, str) or not (governor_hash == "none" or len(governor_hash) == 64):
        raise SystemExit("Smoke test failed: provenance governor_hash must be 'none' or a sha256 hex string.")

    provider_info = prov.get("provider")
    if not isinstance(provider_info, dict):
        raise SystemExit("Smoke test failed: provenance.v1.json provider must be an object.")
    if provider_info.get("provider_used") != summary_file.get("provider_used"):
        raise SystemExit("Smoke test failed: provenance provider_used must match summary provider_used.")

    integrity_manifest_obj = json.loads((evidence_dir / "integrity.manifest.v1.json").read_text(encoding="utf-8"))
    files_list = integrity_manifest_obj.get("files") if isinstance(integrity_manifest_obj, dict) else None
    if not isinstance(files_list, list):
        raise SystemExit("Smoke test failed: integrity.manifest.v1.json files must be a list.")
    prov_entries = [e for e in files_list if isinstance(e, dict) and e.get("path") == "provenance.v1.json"]
    if not prov_entries:
        raise SystemExit("Smoke test failed: integrity manifest must include provenance.v1.json entry.")
    prov_sha = prov_entries[0].get("sha256")
    if not isinstance(prov_sha, str) or len(prov_sha) != 64:
        raise SystemExit("Smoke test failed: integrity manifest provenance sha256 must be a 64-char hex string.")

    policies_hash_prefix = str(fingerprints.get("policies_hash"))[:12]
    print("CRITICAL_PROVENANCE_OK: " + f"run_id={run_id_ok} commit={commit} policies_hash_prefix={policies_hash_prefix}")

    budget_spec = summary_file.get("budget")
    if not isinstance(budget_spec, dict):
        raise SystemExit("Smoke test failed: summary.json budget must be an object.")
    for k in ("max_attempts", "max_time_ms", "max_tokens"):
        if k not in budget_spec:
            raise SystemExit(f"Smoke test failed: summary.json budget missing key: {k}")

    budget_usage = summary_file.get("budget_usage")
    if not isinstance(budget_usage, dict):
        raise SystemExit("Smoke test failed: summary.json budget_usage must be an object.")
    for k in ("attempts_used", "elapsed_ms", "est_tokens_used"):
        if k not in budget_usage:
            raise SystemExit(f"Smoke test failed: summary.json budget_usage missing key: {k}")

    if summary_file.get("budget_hit") is not None:
        raise SystemExit("Smoke test failed: completed run budget_hit must be null.")

    quota_spec = summary_file.get("quota")
    if not isinstance(quota_spec, dict):
        raise SystemExit("Smoke test failed: summary.json quota must be an object.")
    for k in ("max_runs_per_day", "max_est_tokens_per_day"):
        if k not in quota_spec:
            raise SystemExit(f"Smoke test failed: summary.json quota missing key: {k}")

    quota_usage_before = summary_file.get("quota_usage_before")
    quota_usage_after = summary_file.get("quota_usage_after")
    if not isinstance(quota_usage_before, dict) or not isinstance(quota_usage_after, dict):
        raise SystemExit("Smoke test failed: summary.json quota_usage_before/after must be objects.")
    for k in ("runs_used", "est_tokens_used"):
        if k not in quota_usage_before or k not in quota_usage_after:
            raise SystemExit(f"Smoke test failed: quota_usage_before/after missing key: {k}")

    if summary_file.get("quota_hit") is not None:
        raise SystemExit("Smoke test failed: completed run quota_hit must be null.")

    dp = json.loads((repo_root / "orchestrator" / "decision_policy.v1.json").read_text(encoding="utf-8"))
    expected_threshold = float(dp.get("approval_risk_threshold", 0.7))
    if summary_file.get("approval_threshold_used") != expected_threshold:
        raise SystemExit("Smoke test failed: approval_threshold_used mismatch.")

    provider_used = summary_file.get("provider_used")
    model_used = summary_file.get("model_used")
    if provider_used == "stub" and model_used is not None:
        raise SystemExit("Smoke test failed: stub provider must have model_used == null.")
    if provider_used == "openai" and not isinstance(model_used, str):
        raise SystemExit("Smoke test failed: openai provider must have model_used as string.")

    secrets_used = summary_file.get("secrets_used")
    if not isinstance(secrets_used, list):
        raise SystemExit("Smoke test failed: summary.json secrets_used must be a list.")

    store_text = idempotency_store_path.read_text(encoding="utf-8")
    if "TENANT-LOCAL:REQ-0001" in store_text:
        raise SystemExit("Smoke test failed: idempotency store must not contain plaintext idempotency_key.")

    proc2 = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0001.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_ok),
        ]
    )
    summary2 = json.loads(proc2.stdout)
    if summary2.get("status") != "IDEMPOTENT_HIT":
        raise SystemExit(f"Smoke test failed: expected IDEMPOTENT_HIT, got: {summary2.get('status')}")
    if summary2.get("run_id") != run_id:
        raise SystemExit("Smoke test failed: run_id must be identical across idempotent runs.")
    if summary2.get("workflow_fingerprint") != summary_file.get("workflow_fingerprint"):
        raise SystemExit("Smoke test failed: workflow_fingerprint must be stable across idempotent runs.")
    if summary2.get("approval_threshold_used") != expected_threshold:
        raise SystemExit("Smoke test failed: approval_threshold_used must be echoed on idempotent hit.")

    dirs = sorted([p.name for p in out_dir_ok.iterdir() if p.is_dir()])
    if dirs != [run_id]:
        raise SystemExit(f"Smoke test failed: unexpected evidence directories: {dirs}")

    if out_file.exists():
        raise SystemExit("Smoke test failed: dry_run must not create fixtures/out.md (after idempotent hit).")

    # MOD_POLICY_REVIEW: policy review report generation (safe, deterministic, no network).
    policy_review_env_path = repo_root / "fixtures" / "envelopes" / "0900_policy_review.json"
    if not policy_review_env_path.exists():
        raise SystemExit("Smoke test failed: fixtures/envelopes/0900_policy_review.json missing.")

    policy_review_out_file = repo_root / "fixtures" / "policy_review.md"
    if policy_review_out_file.exists():
        policy_review_out_file.unlink()

    out_dir_policy_review = smoke_root / "policy_review"
    if out_dir_policy_review.exists():
        rmtree(out_dir_policy_review)

    proc_policy_review = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(policy_review_env_path),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_policy_review),
        ]
    )
    try:
        summary_pr = json.loads(proc_policy_review.stdout)
    except Exception as e:
        raise SystemExit("Smoke test failed: 0900 policy review stdout must be JSON.\n" + proc_policy_review.stdout) from e

    if summary_pr.get("workflow_id") != "WF_POLICY_REVIEW":
        raise SystemExit("Smoke test failed: 0900 policy review must route to WF_POLICY_REVIEW.")

    if summary_pr.get("result_state") != "COMPLETED":
        raise SystemExit("Smoke test failed: 0900 policy review must complete (dry_run, no approval needed).")

    run_id_pr = summary_pr.get("run_id")
    if not isinstance(run_id_pr, str) or not run_id_pr:
        raise SystemExit("Smoke test failed: 0900 policy review missing run_id.")

    ev_pr = out_dir_policy_review / run_id_pr
    mod_a_out_pr = json.loads((ev_pr / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
    if not isinstance(mod_a_out_pr, dict):
        raise SystemExit("Smoke test failed: 0900 MOD_A output must be a JSON object.")
    if mod_a_out_pr.get("module_id") != "MOD_POLICY_REVIEW":
        raise SystemExit("Smoke test failed: 0900 MOD_A module_id must be MOD_POLICY_REVIEW.")
    if mod_a_out_pr.get("status") != "COMPLETED":
        raise SystemExit("Smoke test failed: 0900 MOD_POLICY_REVIEW must complete.")
    report_bytes_pr = int(mod_a_out_pr.get("report_bytes", 0))
    if report_bytes_pr <= 0:
        raise SystemExit("Smoke test failed: 0900 MOD_POLICY_REVIEW report_bytes must be > 0.")

    side_effects_pr = mod_a_out_pr.get("side_effects")
    if not (isinstance(side_effects_pr, dict) and isinstance(side_effects_pr.get("would_write"), dict)):
        raise SystemExit("Smoke test failed: 0900 MOD_POLICY_REVIEW must record side_effects.would_write (dry_run).")

    tool_calls_pr = mod_a_out_pr.get("tool_calls")
    if not (
        isinstance(tool_calls_pr, list)
        and any(
            isinstance(tc, dict) and tc.get("tool") == "policy_check" and tc.get("status") == "OK"
            for tc in tool_calls_pr
        )
    ):
        raise SystemExit("Smoke test failed: 0900 MOD_POLICY_REVIEW must record a successful policy_check tool_call.")

    report_md_path = repo_root / ".cache" / "policy_review" / "POLICY_REPORT.md"
    if not report_md_path.exists():
        raise SystemExit("Smoke test failed: MOD_POLICY_REVIEW must create .cache/policy_review/POLICY_REPORT.md")

    if policy_review_out_file.exists():
        raise SystemExit("Smoke test failed: policy review dry_run must not create fixtures/policy_review.md")

    print(f"CRITICAL_POLICY_REVIEW: ok=true report_bytes={report_bytes_pr}")

    # MOD_DLQ_TRIAGE: DLQ triage report generation (safe, deterministic, no network).
    dlq_triage_env_path = repo_root / "fixtures" / "envelopes" / "0910_dlq_triage.json"
    if not dlq_triage_env_path.exists():
        raise SystemExit("Smoke test failed: fixtures/envelopes/0910_dlq_triage.json missing.")

    dlq_dir = repo_root / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)

    synth_a = dlq_dir / "99999999_000001_REQ-DLQ-SYNTH-A.json"
    synth_b = dlq_dir / "99999999_000002_REQ-DLQ-SYNTH-B.json"
    for p in (synth_a, synth_b):
        if p.exists():
            p.unlink()

    synth_records = [
        (
            synth_a,
            {
                "stage": "EXECUTION",
                "error_code": "SYNTH_ERROR_A",
                "message": "SYNTH_MSG_ALPHA",
                "envelope": {
                    "request_id": "REQ-DLQ-SYNTH-A",
                    "tenant_id": "TENANT-LOCAL",
                    "intent": "urn:core:summary:summary_to_file",
                    "risk_score": 0.1,
                    "dry_run": True,
                    "side_effect_policy": "none",
                    "idempotency_key_hash": "synth",
                },
                "ts": "2000-01-01T00:00:00Z",
            },
        ),
        (
            synth_b,
            {
                "stage": "BUDGET",
                "error_code": "SYNTH_ERROR_B",
                "message": "SYNTH_MSG_BETA",
                "envelope": {
                    "request_id": "REQ-DLQ-SYNTH-B",
                    "tenant_id": "TENANT-LOCAL",
                    "intent": "urn:core:summary:summary_to_file",
                    "risk_score": 0.9,
                    "dry_run": True,
                    "side_effect_policy": "none",
                    "idempotency_key_hash": "synth",
                },
                "ts": "2000-01-01T00:00:01Z",
            },
        ),
    ]
    for p, obj in synth_records:
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    dlq_triage_out_file = repo_root / "dlq_triage.md"
    if dlq_triage_out_file.exists():
        dlq_triage_out_file.unlink()

    out_dir_dlq_triage = smoke_root / "dlq_triage"
    if out_dir_dlq_triage.exists():
        rmtree(out_dir_dlq_triage)

    try:
        proc_dlq_triage = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(dlq_triage_env_path),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_dlq_triage),
            ]
        )
        try:
            summary_dt = json.loads(proc_dlq_triage.stdout)
        except Exception as e:
            raise SystemExit(
                "Smoke test failed: 0910 dlq triage stdout must be JSON.\n" + proc_dlq_triage.stdout
            ) from e

        if summary_dt.get("result_state") != "COMPLETED":
            raise SystemExit("Smoke test failed: 0910 dlq triage must complete (dry_run, no approval needed).")

        if summary_dt.get("workflow_id") != "WF_DLQ_TRIAGE":
            raise SystemExit("Smoke test failed: 0910 dlq triage must route to WF_DLQ_TRIAGE.")

        run_id_dt = summary_dt.get("run_id")
        if not isinstance(run_id_dt, str) or not run_id_dt:
            raise SystemExit("Smoke test failed: 0910 dlq triage missing run_id.")

        ev_dt = out_dir_dlq_triage / run_id_dt
        mod_a_out_dt = json.loads((ev_dt / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
        if not isinstance(mod_a_out_dt, dict):
            raise SystemExit("Smoke test failed: 0910 MOD_A output must be a JSON object.")
        if mod_a_out_dt.get("module_id") != "MOD_DLQ_TRIAGE":
            raise SystemExit("Smoke test failed: 0910 MOD_A module_id must be MOD_DLQ_TRIAGE.")
        if mod_a_out_dt.get("status") != "COMPLETED":
            raise SystemExit("Smoke test failed: 0910 MOD_DLQ_TRIAGE must complete.")

        items_scanned = int(mod_a_out_dt.get("items_scanned", 0))
        if items_scanned < 2:
            raise SystemExit("Smoke test failed: 0910 MOD_DLQ_TRIAGE items_scanned must be >= 2.")

        report_bytes_dt = int(mod_a_out_dt.get("report_bytes", 0))
        if report_bytes_dt <= 0:
            raise SystemExit("Smoke test failed: 0910 MOD_DLQ_TRIAGE report_bytes must be > 0.")

        side_effects_dt = mod_a_out_dt.get("side_effects")
        if not (isinstance(side_effects_dt, dict) and isinstance(side_effects_dt.get("would_write"), dict)):
            raise SystemExit("Smoke test failed: 0910 MOD_DLQ_TRIAGE must record side_effects.would_write (dry_run).")

        counts_by_error = mod_a_out_dt.get("counts_by_error_code")
        if not (
            isinstance(counts_by_error, dict)
            and int(counts_by_error.get("SYNTH_ERROR_A", 0)) >= 1
            and int(counts_by_error.get("SYNTH_ERROR_B", 0)) >= 1
        ):
            raise SystemExit("Smoke test failed: 0910 counts_by_error_code must include synthetic error codes.")

        tc_dt = mod_a_out_dt.get("tool_calls")
        if not (
            isinstance(tc_dt, list)
            and any(isinstance(tc, dict) and tc.get("tool") == "dlq_triage" and tc.get("status") == "OK" for tc in tc_dt)
        ):
            raise SystemExit("Smoke test failed: 0910 MOD_DLQ_TRIAGE must record a successful dlq_triage tool_call.")

        if dlq_triage_out_file.exists():
            raise SystemExit("Smoke test failed: dlq triage dry_run must not create dlq_triage.md")

        print(f"CRITICAL_DLQ_TRIAGE: ok=true items_scanned={items_scanned} report_bytes={report_bytes_dt}")
    finally:
        for p in (synth_a, synth_b):
            if p.exists():
                p.unlink()

    print("CRITICAL_WORKFLOW_ROUTING: policy_review=WF_POLICY_REVIEW dlq_triage=WF_DLQ_TRIAGE")

    # GitHub PR side-effect (v0.1): deterministic dry-run plan + fail-closed live mode.
    pr_dry_env_path = repo_root / "fixtures" / "envelopes" / "0920_pr_side_effect_dry.json"
    if not pr_dry_env_path.exists():
        raise SystemExit("Smoke test failed: fixtures/envelopes/0920_pr_side_effect_dry.json missing.")

    out_dir_pr_dry = smoke_root / "pr_side_effect_dry"
    if out_dir_pr_dry.exists():
        rmtree(out_dir_pr_dry)

    proc_pr_dry = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(pr_dry_env_path),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_pr_dry),
        ]
    )
    try:
        summary_pr_dry = json.loads(proc_pr_dry.stdout)
    except Exception as e:
        raise SystemExit("Smoke test failed: 0920 pr dry stdout must be JSON.\n" + proc_pr_dry.stdout) from e

    if summary_pr_dry.get("result_state") != "COMPLETED":
        raise SystemExit("Smoke test failed: 0920 pr dry must complete (dry_run=true).")

    run_id_pr_dry = summary_pr_dry.get("run_id")
    if not isinstance(run_id_pr_dry, str) or not run_id_pr_dry:
        raise SystemExit("Smoke test failed: 0920 pr dry missing run_id.")

    ev_pr_dry = out_dir_pr_dry / run_id_pr_dry
    mod_b_out_pr_dry = json.loads((ev_pr_dry / "nodes" / "MOD_B" / "output.json").read_text(encoding="utf-8"))
    side_effects_pr_dry = mod_b_out_pr_dry.get("side_effects") if isinstance(mod_b_out_pr_dry, dict) else None
    if not (isinstance(side_effects_pr_dry, dict) and isinstance(side_effects_pr_dry.get("would_pr_create"), dict)):
        raise SystemExit("Smoke test failed: 0920 MOD_B must record side_effects.would_pr_create (dry_run).")

    pr_live_env_path = repo_root / "fixtures" / "envelopes" / "0921_pr_side_effect_live_blocked.json"
    if not pr_live_env_path.exists():
        raise SystemExit("Smoke test failed: fixtures/envelopes/0921_pr_side_effect_live_blocked.json missing.")

    out_dir_pr_live = smoke_root / "pr_side_effect_live"
    if out_dir_pr_live.exists():
        rmtree(out_dir_pr_live)

    dlq_before_pr = set(dlq_dir.glob("*.json"))
    pr_env = dict(os.environ)
    pr_env.pop("ORCH_INTEGRATION_MODE", None)
    pr_env.pop("GITHUB_TOKEN", None)
    proc_pr_live = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(pr_live_env_path),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_pr_live),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=pr_env,
    )
    try:
        summary_pr_live = json.loads(proc_pr_live.stdout)
    except Exception as e:
        raise SystemExit("Smoke test failed: 0921 pr live stdout must be JSON.\n" + proc_pr_live.stdout) from e

    run_id_pr_live = summary_pr_live.get("run_id")
    if not isinstance(run_id_pr_live, str) or not run_id_pr_live:
        raise SystemExit("Smoke test failed: 0921 pr live missing run_id.")

    # Depending on autonomy gating, the initial run may SUSPEND. Resume with approval to trigger MOD_B.
    ev_pr_live = out_dir_pr_live / run_id_pr_live
    if (ev_pr_live / "summary.json").exists():
        summary_pr_live_file = json.loads((ev_pr_live / "summary.json").read_text(encoding="utf-8"))
    else:
        summary_pr_live_file = summary_pr_live

    if summary_pr_live_file.get("result_state") == "SUSPENDED":
        proc_pr_resume = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--resume",
                str(ev_pr_live),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_pr_live),
                "--approve",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=pr_env,
        )
        if proc_pr_resume.returncode == 0:
            raise SystemExit("Smoke test failed: 0921 resume must fail closed without integration mode.")

    summary_pr_live_after = json.loads((ev_pr_live / "summary.json").read_text(encoding="utf-8"))
    if summary_pr_live_after.get("result_state") != "FAILED":
        raise SystemExit("Smoke test failed: 0921 pr live must end as FAILED (integration blocked).")
    if summary_pr_live_after.get("policy_violation_code") != "INTEGRATION_MODE_REQUIRED":
        raise SystemExit(
            "Smoke test failed: 0921 pr live must fail with INTEGRATION_MODE_REQUIRED, got: "
            + str(summary_pr_live_after.get("policy_violation_code"))
        )

    dlq_after_pr = set(dlq_dir.glob("*.json"))
    new_pr_dlq = sorted(dlq_after_pr - dlq_before_pr, key=lambda p: p.name)
    if not new_pr_dlq:
        raise SystemExit("Smoke test failed: 0921 pr live must create a DLQ record under dlq/.")

    latest_pr_dlq = max(new_pr_dlq, key=lambda p: p.stat().st_mtime)
    dlq_pr = json.loads(latest_pr_dlq.read_text(encoding="utf-8"))
    if dlq_pr.get("stage") != "EXECUTION" or dlq_pr.get("error_code") != "POLICY_VIOLATION":
        raise SystemExit("Smoke test failed: 0921 pr live DLQ must be EXECUTION/POLICY_VIOLATION.")
    if "INTEGRATION_MODE_REQUIRED" not in str(dlq_pr.get("message", "")):
        raise SystemExit("Smoke test failed: 0921 pr live DLQ message must include INTEGRATION_MODE_REQUIRED.")

    mod_b_out_pr_live = json.loads((ev_pr_live / "nodes" / "MOD_B" / "output.json").read_text(encoding="utf-8"))
    tc_pr_live = mod_b_out_pr_live.get("tool_calls") if isinstance(mod_b_out_pr_live, dict) else None
    if not (
        isinstance(tc_pr_live, list)
        and any(isinstance(tc, dict) and tc.get("tool") == "github_pr_create" and tc.get("error_code") == "INTEGRATION_MODE_REQUIRED" for tc in tc_pr_live)
    ):
        raise SystemExit("Smoke test failed: 0921 MOD_B tool_calls must include github_pr_create error_code INTEGRATION_MODE_REQUIRED.")

    print("CRITICAL_PR_SIDE_EFFECT: dry_plan=true live_blocked=true")

    # CLI shortcut: orchestrator run --intent ... (no envelope file needed).
    cli_policy_review_out_file = repo_root / "policy_review.md"
    if cli_policy_review_out_file.exists():
        cli_policy_review_out_file.unlink()

    out_dir_cli = smoke_root / "cli_run"
    if out_dir_cli.exists():
        rmtree(out_dir_cli)

    proc_cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli",
            "run",
            "--intent",
            "urn:core:docs:policy_review",
            "--tenant",
            "TENANT-LOCAL",
            "--dry-run",
            "true",
            "--output-path",
            "policy_review.md",
            "--workspace",
            str(repo_root),
            "--evidence",
            str(out_dir_cli.relative_to(repo_root)),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_cli.returncode != 0:
        raise SystemExit(
            "Smoke test failed: cli run shortcut must exit 0.\n"
            + (proc_cli.stderr or proc_cli.stdout or "")
        )

    try:
        cli_obj = json.loads((proc_cli.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: cli run shortcut must output JSON.\n" + (proc_cli.stdout or "")) from e

    run_id_cli = cli_obj.get("run_id") if isinstance(cli_obj, dict) else None
    evidence_path_cli = cli_obj.get("evidence_path") if isinstance(cli_obj, dict) else None
    if not isinstance(run_id_cli, str) or not run_id_cli:
        raise SystemExit("Smoke test failed: cli run shortcut output missing run_id.")
    if not isinstance(evidence_path_cli, str) or not evidence_path_cli:
        raise SystemExit("Smoke test failed: cli run shortcut output missing evidence_path.")

    run_dir_cli = repo_root / evidence_path_cli
    if not (run_dir_cli / "summary.json").exists():
        raise SystemExit("Smoke test failed: cli run must create evidence/<run_id>/summary.json")

    sum_cli = json.loads((run_dir_cli / "summary.json").read_text(encoding="utf-8"))
    if sum_cli.get("result_state") != "COMPLETED":
        raise SystemExit("Smoke test failed: cli policy review run must complete (dry_run=true).")

    mod_b_out_cli = json.loads((run_dir_cli / "nodes" / "MOD_B" / "output.json").read_text(encoding="utf-8"))
    side_effects_cli = mod_b_out_cli.get("side_effects") if isinstance(mod_b_out_cli, dict) else None
    if not (isinstance(side_effects_cli, dict) and isinstance(side_effects_cli.get("would_write"), dict)):
        raise SystemExit("Smoke test failed: cli policy review run must be dry-run (would_write missing).")

    if cli_policy_review_out_file.exists():
        raise SystemExit("Smoke test failed: cli policy review dry_run must not create policy_review.md")

    print(f"CRITICAL_CLI_RUN_SHORTCUT: ok=true run_id={run_id_cli}")

    # Replay v0.1: replay an existing run from evidence/request.json into a NEW run.
    out_dir_replay = smoke_root / "replay"
    if out_dir_replay.exists():
        rmtree(out_dir_replay)

    proc_replay = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--replay",
            str(evidence_dir_ok),
            "--force-new-run",
            "true",
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_replay),
        ]
    )
    replay_summary = json.loads(proc_replay.stdout)
    replay_run_id = replay_summary.get("run_id")
    if not isinstance(replay_run_id, str) or not replay_run_id:
        raise SystemExit("Smoke test failed: replay run must output run_id.")
    if replay_run_id == run_id_ok:
        raise SystemExit("Smoke test failed: replay --force-new-run must create a different run_id.")

    replay_of = replay_summary.get("replay_of")
    if replay_of != run_id_ok:
        raise SystemExit("Smoke test failed: replay summary must include replay_of=old run_id.")

    replay_warnings = replay_summary.get("replay_warnings")
    if not isinstance(replay_warnings, list):
        raise SystemExit("Smoke test failed: replay summary replay_warnings must be a list.")

    replay_evidence_dir = out_dir_replay / replay_run_id
    if not (replay_evidence_dir / "summary.json").exists():
        raise SystemExit("Smoke test failed: replay evidence must include summary.json")
    replay_summary_file = json.loads((replay_evidence_dir / "summary.json").read_text(encoding="utf-8"))
    if replay_summary_file.get("replay_of") != run_id_ok:
        raise SystemExit("Smoke test failed: replay evidence summary.json replay_of mismatch.")

    print(
        "CRITICAL_REPLAY: "
        + f"old={run_id_ok} "
        + f"new={replay_run_id} "
        + f"warnings={len(replay_warnings)}"
    )

    dlq_dir = repo_root / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)

    # Optional: JIT secrets + network policy stub (deterministic, no network required).
    fixture_0820 = repo_root / "fixtures" / "envelopes" / "0820_network_disabled.json"
    if fixture_0820.exists():
        out_dir_net = smoke_root / "network_policy"
        dlq_before_net = set(dlq_dir.glob("*.json"))
        proc_net = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(fixture_0820),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_net),
            ],
            text=True,
            capture_output=True,
        )

        have_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        try:
            summary_net = json.loads(proc_net.stdout)
        except Exception as e:
            raise SystemExit("Smoke test failed: 0820 stdout must be JSON.\n" + proc_net.stdout) from e

        run_id_net = summary_net.get("run_id")
        if not isinstance(run_id_net, str) or not run_id_net:
            raise SystemExit("Smoke test failed: 0820 summary missing run_id.")

        evidence_net = out_dir_net / run_id_net
        mod_a_out_net = json.loads((evidence_net / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
        tc_net = mod_a_out_net.get("tool_calls") if isinstance(mod_a_out_net, dict) else None
        secrets_call = None
        if isinstance(tc_net, list):
            for tc in tc_net:
                if isinstance(tc, dict) and tc.get("tool") == "secrets_get":
                    secrets_call = tc
                    break

        if secrets_call is None:
            raise SystemExit("Smoke test failed: 0820 MOD_A must record a secrets_get tool_call.")
        if secrets_call.get("redacted") is not True:
            raise SystemExit("Smoke test failed: secrets_get tool_call must be redacted=true.")

        if have_key:
            if proc_net.returncode == 0:
                raise SystemExit("Smoke test failed: 0820 must fail with OPENAI_API_KEY present (NETWORK_DISABLED).")
            if summary_net.get("policy_violation_code") != "NETWORK_DISABLED":
                raise SystemExit(
                    "Smoke test failed: 0820 must set policy_violation_code=NETWORK_DISABLED.\n"
                    + json.dumps(summary_net, indent=2, ensure_ascii=False)
                )
            if summary_net.get("provider_used") != "openai":
                raise SystemExit("Smoke test failed: 0820 should record provider_used=openai on NETWORK_DISABLED.")
            secrets_used_net = summary_net.get("secrets_used")
            if not (isinstance(secrets_used_net, list) and "OPENAI_API_KEY" in secrets_used_net):
                raise SystemExit("Smoke test failed: 0820 must record secrets_used including OPENAI_API_KEY.")

            dlq_after_net = set(dlq_dir.glob("*.json"))
            new_net_dlq = sorted(dlq_after_net - dlq_before_net, key=lambda p: p.name)
            if not new_net_dlq:
                raise SystemExit("Smoke test failed: 0820 NETWORK_DISABLED must create a DLQ record under dlq/.")
            latest_net_dlq = max(new_net_dlq, key=lambda p: p.stat().st_mtime)
            dlq_net = json.loads(latest_net_dlq.read_text(encoding="utf-8"))
            if dlq_net.get("stage") != "EXECUTION" or dlq_net.get("error_code") != "POLICY_VIOLATION":
                raise SystemExit("Smoke test failed: 0820 DLQ must be EXECUTION/POLICY_VIOLATION.")
            if "NETWORK_DISABLED" not in str(dlq_net.get("message", "")):
                raise SystemExit("Smoke test failed: 0820 DLQ message must mention NETWORK_DISABLED.")

            # Capture for critical evidence snapshot.
            network_run_id_for_snapshot = run_id_net
            network_dlq_path_for_snapshot = latest_net_dlq
            network_policy_violation_code_for_snapshot = summary_net.get("policy_violation_code")
        else:
            if proc_net.returncode != 0:
                raise SystemExit(
                    "Smoke test failed: 0820 must succeed with no OPENAI_API_KEY set.\n"
                    + proc_net.stdout
                    + "\n"
                    + proc_net.stderr
                )
            if summary_net.get("provider_used") != "stub" or summary_net.get("model_used") is not None:
                raise SystemExit("Smoke test failed: 0820 must use stub provider with no OPENAI_API_KEY set.")
            secrets_used_net = summary_net.get("secrets_used")
            if not (isinstance(secrets_used_net, list) and secrets_used_net == []):
                raise SystemExit("Smoke test failed: 0820 must keep secrets_used empty when no OPENAI_API_KEY set.")

            network_run_id_for_snapshot = run_id_net
            network_dlq_path_for_snapshot = None
            network_policy_violation_code_for_snapshot = None

        # Deterministic secrets provider test: vault_stub provider (no real Vault).
        # - Provide a fake key via .cache/vault_stub_secrets.json
        # - Force provider selection via policies/policy_secrets.v1.json
        # Expectation: secret retrieval succeeds but NETWORK_DISABLED still blocks OpenAI usage.
        policy_secrets_path = repo_root / "policies" / "policy_secrets.v1.json"
        vault_stub_path = repo_root / ".cache" / "vault_stub_secrets.json"
        policy_security_path = repo_root / "policies" / "policy_security.v1.json"
        original_policy_secrets = policy_secrets_path.read_text(encoding="utf-8") if policy_secrets_path.exists() else None
        original_policy_security = policy_security_path.read_text(encoding="utf-8") if policy_security_path.exists() else None

        try:
            policy_secrets_path.write_text(
                json.dumps(
                    {"version": "v1", "provider": "vault_stub", "allowed_secret_ids": ["OPENAI_API_KEY"]},
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            vault_stub_path.parent.mkdir(parents=True, exist_ok=True)
            vault_stub_path.write_text(
                json.dumps({"OPENAI_API_KEY": "TESTKEY"}, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            out_dir_vault = smoke_root / "secrets_vault_stub"
            dlq_before_vault = set(dlq_dir.glob("*.json"))
            proc_vault = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.orchestrator.local_runner",
                    "--envelope",
                    str(fixture_0820),
                    "--workspace",
                    str(repo_root),
                    "--out",
                    str(out_dir_vault),
                ],
                text=True,
                capture_output=True,
            )

            if proc_vault.returncode == 0:
                raise SystemExit("Smoke test failed: 0820 must fail under vault_stub (NETWORK_DISABLED).")

            try:
                summary_vault = json.loads(proc_vault.stdout)
            except Exception as e:
                raise SystemExit("Smoke test failed: vault_stub 0820 stdout must be JSON.\n" + proc_vault.stdout) from e

            run_id_vault = summary_vault.get("run_id")
            if not isinstance(run_id_vault, str) or not run_id_vault:
                raise SystemExit("Smoke test failed: vault_stub 0820 summary missing run_id.")
            if summary_vault.get("policy_violation_code") != "NETWORK_DISABLED":
                raise SystemExit("Smoke test failed: vault_stub 0820 must set policy_violation_code=NETWORK_DISABLED.")
            secrets_used_vault = summary_vault.get("secrets_used")
            if not (isinstance(secrets_used_vault, list) and "OPENAI_API_KEY" in secrets_used_vault):
                raise SystemExit("Smoke test failed: vault_stub 0820 must record secrets_used including OPENAI_API_KEY.")

            evidence_vault = out_dir_vault / run_id_vault
            mod_a_out_vault = json.loads((evidence_vault / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
            tc_vault = mod_a_out_vault.get("tool_calls") if isinstance(mod_a_out_vault, dict) else None
            secrets_tc_vault = None
            if isinstance(tc_vault, list):
                for tc in tc_vault:
                    if isinstance(tc, dict) and tc.get("tool") == "secrets_get":
                        secrets_tc_vault = tc
                        break
            if secrets_tc_vault is None:
                raise SystemExit("Smoke test failed: vault_stub 0820 must record secrets_get tool_call in MOD_A output.")
            if secrets_tc_vault.get("redacted") is not True:
                raise SystemExit("Smoke test failed: vault_stub secrets_get tool_call must be redacted=true.")
            if secrets_tc_vault.get("provider_used") != "vault_stub":
                raise SystemExit("Smoke test failed: vault_stub secrets_get tool_call must include provider_used=vault_stub.")

            net_tc_vault = None
            if isinstance(tc_vault, list):
                for tc in tc_vault:
                    if isinstance(tc, dict) and tc.get("tool") == "network_check":
                        net_tc_vault = tc
                        break
            if net_tc_vault is None:
                raise SystemExit("Smoke test failed: 0820 vault_stub must record network_check tool_call.")
            if net_tc_vault.get("status") != "FAIL" or net_tc_vault.get("error_code") != "NETWORK_DISABLED":
                raise SystemExit("Smoke test failed: 0820 vault_stub network_check must fail with NETWORK_DISABLED.")

            dlq_after_vault = set(dlq_dir.glob("*.json"))
            new_vault_dlq = sorted(dlq_after_vault - dlq_before_vault, key=lambda p: p.name)
            if not new_vault_dlq:
                raise SystemExit("Smoke test failed: vault_stub 0820 must create a DLQ record.")
            latest_vault_dlq = max(new_vault_dlq, key=lambda p: p.stat().st_mtime)

            print(
                "CRITICAL_SECRETS_PROVIDER: "
                + "provider=vault_stub "
                + "secrets_used=['OPENAI_API_KEY'] "
                + "network_blocked=true "
                + f"dlq_file={latest_vault_dlq.name}"
            )

            # Network allowlist enforcement: network_access=true but allowlist empty => NETWORK_HOST_NOT_ALLOWED.
            fixture_0870 = repo_root / "fixtures" / "envelopes" / "0870_network_host_not_allowed.json"
            if not fixture_0870.exists():
                raise SystemExit("Smoke test failed: fixtures/envelopes/0870_network_host_not_allowed.json missing.")
            if original_policy_security is None:
                raise SystemExit("Smoke test failed: policies/policy_security.v1.json missing.")

            try:
                sec_obj = json.loads(original_policy_security)
            except Exception as e:
                raise SystemExit("Smoke test failed: policy_security.v1.json must be valid JSON.") from e
            if not isinstance(sec_obj, dict):
                raise SystemExit("Smoke test failed: policy_security.v1.json must be a JSON object.")
            sec_obj["network_access"] = True
            sec_obj["network_allowlist"] = []
            policy_security_path.write_text(json.dumps(sec_obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

            out_dir_0870 = smoke_root / "network_host_not_allowed"
            dlq_before_0870 = set(dlq_dir.glob("*.json"))
            proc_0870 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.orchestrator.local_runner",
                    "--envelope",
                    str(fixture_0870),
                    "--workspace",
                    str(repo_root),
                    "--out",
                    str(out_dir_0870),
                ],
                text=True,
                capture_output=True,
            )
            if proc_0870.returncode == 0:
                raise SystemExit("Smoke test failed: 0870 must fail with NETWORK_HOST_NOT_ALLOWED.")
            try:
                summary_0870 = json.loads(proc_0870.stdout)
            except Exception as e:
                raise SystemExit("Smoke test failed: 0870 stdout must be JSON.\n" + proc_0870.stdout) from e
            if summary_0870.get("policy_violation_code") != "NETWORK_HOST_NOT_ALLOWED":
                raise SystemExit("Smoke test failed: 0870 must set policy_violation_code=NETWORK_HOST_NOT_ALLOWED.")
            secrets_used_0870 = summary_0870.get("secrets_used")
            if not (isinstance(secrets_used_0870, list) and "OPENAI_API_KEY" in secrets_used_0870):
                raise SystemExit("Smoke test failed: 0870 must record secrets_used including OPENAI_API_KEY.")

            run_id_0870 = summary_0870.get("run_id")
            if not isinstance(run_id_0870, str) or not run_id_0870:
                raise SystemExit("Smoke test failed: 0870 summary missing run_id.")
            ev_0870 = out_dir_0870 / run_id_0870
            mod_a_out_0870 = json.loads((ev_0870 / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
            tc_0870 = mod_a_out_0870.get("tool_calls") if isinstance(mod_a_out_0870, dict) else None
            net_tc_0870 = None
            if isinstance(tc_0870, list):
                for tc in tc_0870:
                    if isinstance(tc, dict) and tc.get("tool") == "network_check":
                        net_tc_0870 = tc
                        break
            if net_tc_0870 is None:
                raise SystemExit("Smoke test failed: 0870 must record network_check tool_call.")
            if net_tc_0870.get("status") != "FAIL" or net_tc_0870.get("error_code") != "NETWORK_HOST_NOT_ALLOWED":
                raise SystemExit("Smoke test failed: 0870 network_check must fail with NETWORK_HOST_NOT_ALLOWED.")

            dlq_after_0870 = set(dlq_dir.glob("*.json"))
            new_0870_dlq = sorted(dlq_after_0870 - dlq_before_0870, key=lambda p: p.name)
            if not new_0870_dlq:
                raise SystemExit("Smoke test failed: 0870 must create a DLQ record.")

            print("CRITICAL_NETWORK_POLICY: disabled=true host_not_allowed=true")
        finally:
            if original_policy_secrets is None:
                if policy_secrets_path.exists():
                    policy_secrets_path.unlink()
            else:
                policy_secrets_path.write_text(original_policy_secrets, encoding="utf-8")
            if vault_stub_path.exists():
                vault_stub_path.unlink()
            if original_policy_security is not None:
                policy_security_path.write_text(original_policy_security, encoding="utf-8")
    else:
        network_run_id_for_snapshot = None
        network_dlq_path_for_snapshot = None
        network_policy_violation_code_for_snapshot = None

    # Progressive autonomy v0.1: promote to full_auto deterministically (no network required).
    autonomy_promotion_intent_for_snapshot = "urn:core:summary:summary_to_file"
    autonomy_promotion_snapshot_for_snapshot: dict | None = None
    autonomy_used_run_id_for_snapshot: str | None = None
    autonomy_used_mode_for_snapshot: str | None = None
    autonomy_used_gate_for_snapshot: str | None = None

    if autonomy_store_path.exists():
        autonomy_store_path.unlink()

    out_dir_autonomy = smoke_root / "autonomy_promotion"
    for fname in (
        "0860_autonomy_success_1.json",
        "0861_autonomy_success_2.json",
        "0862_autonomy_success_3.json",
    ):
        env_path = repo_root / "fixtures" / "envelopes" / fname
        if not env_path.exists():
            raise SystemExit(f"Smoke test failed: fixtures/envelopes/{fname} missing.")
        proc_auto = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(env_path),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_autonomy),
            ]
        )
        try:
            sum_auto = json.loads(proc_auto.stdout)
        except Exception as e:
            raise SystemExit(f"Smoke test failed: {fname} stdout must be JSON.\n" + proc_auto.stdout) from e
        if sum_auto.get("result_state") != "COMPLETED":
            raise SystemExit(f"Smoke test failed: {fname} must complete for autonomy promotion.")

    if not autonomy_store_path.exists():
        raise SystemExit("Smoke test failed: autonomy store must be created at .cache/autonomy_store.v1.json.")
    autonomy_store = json.loads(autonomy_store_path.read_text(encoding="utf-8"))
    if not isinstance(autonomy_store, dict):
        raise SystemExit("Smoke test failed: autonomy store must be a JSON object.")
    record = autonomy_store.get(autonomy_promotion_intent_for_snapshot)
    if not isinstance(record, dict):
        raise SystemExit("Smoke test failed: autonomy store missing intent record for promotion intent.")

    mode = record.get("mode")
    try:
        samples = int(record.get("samples", 0))
    except Exception:
        samples = 0
    try:
        successes = int(record.get("successes", 0))
    except Exception:
        successes = 0

    if mode != "full_auto":
        raise SystemExit(
            "Smoke test failed: autonomy mode should promote to full_auto after 3 successes.\n"
            + json.dumps(record, indent=2, ensure_ascii=False)
        )

    autonomy_promotion_snapshot_for_snapshot = {"samples": samples, "successes": successes, "mode": mode}

    # After promotion, a low-risk real-write run must NOT be suspended due to autonomy.
    autonomy_write_path = repo_root / "fixtures" / "autonomy_write.md"
    if autonomy_write_path.exists():
        autonomy_write_path.unlink()

    autonomy_low_risk_envelope_path = smoke_root / "0863_autonomy_lowrisk_write.json"
    autonomy_low_risk_envelope = {
        "request_id": "REQ-0863",
        "tenant_id": "TENANT-LOCAL",
        "intent": autonomy_promotion_intent_for_snapshot,
        "risk_score": 0.1,
        "dry_run": False,
        "side_effect_policy": "draft",
        "idempotency_key": "TENANT-LOCAL:REQ-0863",
        "budget": {"max_tokens": 2000, "max_attempts": 2},
        "context": {"input_path": "fixtures/sample.md", "output_path": "fixtures/autonomy_write.md"},
    }
    autonomy_low_risk_envelope_path.write_text(
        json.dumps(autonomy_low_risk_envelope, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    try:
        out_dir_autonomy_write = smoke_root / "autonomy_lowrisk_write"
        proc_aw = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(autonomy_low_risk_envelope_path),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_autonomy_write),
            ]
        )
        sum_aw = json.loads(proc_aw.stdout)
        if sum_aw.get("result_state") != "COMPLETED":
            raise SystemExit("Smoke test failed: low-risk autonomy run must complete (no SUSPEND).")
        run_id_aw = sum_aw.get("run_id")
        if not isinstance(run_id_aw, str) or not run_id_aw:
            raise SystemExit("Smoke test failed: low-risk autonomy run missing run_id.")

        aw_dir = out_dir_autonomy_write / run_id_aw
        aw_summary = json.loads((aw_dir / "summary.json").read_text(encoding="utf-8"))
        if aw_summary.get("autonomy_mode_used") != "full_auto":
            raise SystemExit("Smoke test failed: autonomy_mode_used must be full_auto after promotion.")
        if aw_summary.get("autonomy_gate_triggered") is not None:
            raise SystemExit("Smoke test failed: autonomy_gate_triggered must be null for full_auto run.")
        if not autonomy_write_path.exists():
            raise SystemExit("Smoke test failed: low-risk autonomy run must write fixtures/autonomy_write.md.")

        autonomy_used_run_id_for_snapshot = run_id_aw
        autonomy_used_mode_for_snapshot = aw_summary.get("autonomy_mode_used")
        autonomy_used_gate_for_snapshot = aw_summary.get("autonomy_gate_triggered")
    finally:
        if autonomy_low_risk_envelope_path.exists():
            autonomy_low_risk_envelope_path.unlink()
        if autonomy_write_path.exists():
            autonomy_write_path.unlink()

    out_dir_bad = smoke_root / "invalid"
    dlq_before = set(dlq_dir.glob("*.json"))

    proc_bad = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0999_invalid.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_bad),
        ],
        text=True,
        capture_output=True,
    )
    if proc_bad.returncode == 0:
        raise SystemExit(
            "Smoke test failed: invalid envelope should cause non-zero exit.\n"
            + proc_bad.stdout
            + "\n"
            + proc_bad.stderr
        )

    if out_dir_bad.exists():
        raise SystemExit("Smoke test failed: invalid envelope must not create any evidence output.")

    dlq_after = set(dlq_dir.glob("*.json"))
    new_dlq_files = sorted(dlq_after - dlq_before, key=lambda p: p.name)
    if not new_dlq_files:
        raise SystemExit("Smoke test failed: invalid envelope must create a DLQ record under dlq/.")

    latest_dlq = max(new_dlq_files, key=lambda p: p.stat().st_mtime)
    dlq_record = json.loads(latest_dlq.read_text(encoding="utf-8"))
    for k in ("stage", "error_code", "message", "envelope", "ts"):
        if k not in dlq_record:
            raise SystemExit(f"Smoke test failed: DLQ record missing key: {k}")

    if dlq_record.get("stage") != "ENVELOPE_VALIDATE":
        raise SystemExit("Smoke test failed: DLQ stage should be ENVELOPE_VALIDATE for invalid envelope.")
    if dlq_record.get("error_code") != "SCHEMA_INVALID":
        raise SystemExit("Smoke test failed: DLQ error_code should be SCHEMA_INVALID for invalid envelope.")

    env_min = dlq_record.get("envelope")
    if not isinstance(env_min, dict):
        raise SystemExit("Smoke test failed: DLQ envelope field must be an object.")
    if "idempotency_key" in env_min:
        raise SystemExit("Smoke test failed: DLQ envelope must not include plaintext idempotency_key.")

    failure_run_id_for_snapshot: str | None = None
    failure_dlq_path_for_snapshot: Path | None = None
    failure_dlq_record_for_snapshot: dict | None = None
    budget_tokens_dlq: Path | None = None
    budget_tokens_summary: dict | None = None
    budget_time_dlq: Path | None = None
    budget_time_summary: dict | None = None
    quota_pass_run_id: str | None = None
    quota_pass_usage_after: dict | None = None
    quota_fail_dlq: Path | None = None
    quota_fail_code: str | None = None
    quota_store_date: str | None = None
    quota_store_tenant_snapshot: dict | None = None

    # Path traversal policy violation should fail and create DLQ entry (EXECUTION/POLICY_VIOLATION)
    pwn_path = (repo_root / ".." / "pwn.md").resolve()
    if pwn_path.exists():
        raise SystemExit(f"Smoke test failed: pre-existing {pwn_path} blocks traversal test; remove it and retry.")

    out_dir_traversal = smoke_root / "path_traversal"
    dlq_before_exec = set(dlq_dir.glob("*.json"))
    proc_trav = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0810_path_traversal.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_traversal),
        ],
        text=True,
        capture_output=True,
    )
    if proc_trav.returncode == 0:
        raise SystemExit("Smoke test failed: path traversal run must exit non-zero.")

    dlq_after_exec = set(dlq_dir.glob("*.json"))
    new_exec_dlq = sorted(dlq_after_exec - dlq_before_exec, key=lambda p: p.name)
    if not new_exec_dlq:
        raise SystemExit("Smoke test failed: policy violation must create a DLQ record under dlq/.")

    latest_exec_dlq = max(new_exec_dlq, key=lambda p: p.stat().st_mtime)
    dlq_exec = json.loads(latest_exec_dlq.read_text(encoding="utf-8"))
    if dlq_exec.get("stage") != "EXECUTION":
        raise SystemExit("Smoke test failed: policy violation DLQ stage must be EXECUTION.")
    if dlq_exec.get("error_code") != "POLICY_VIOLATION":
        raise SystemExit("Smoke test failed: policy violation DLQ error_code must be POLICY_VIOLATION.")

    if pwn_path.exists():
        raise SystemExit("Smoke test failed: ../pwn.md must not be created by traversal attempt.")

    # Write too large should fail with POLICY_VIOLATION/WRITE_TOO_LARGE (MOD_B fs_write)
    out_dir_write_large = smoke_root / "write_too_large"
    dlq_before_write_large = set(dlq_dir.glob("*.json"))
    proc_write_large = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0811_write_too_large.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_write_large),
        ],
        text=True,
        capture_output=True,
    )
    if proc_write_large.returncode == 0:
        raise SystemExit("Smoke test failed: write-too-large run must exit non-zero.")
    try:
        summary_write_large = json.loads(proc_write_large.stdout)
    except Exception as e:
        raise SystemExit("Smoke test failed: write-too-large stdout must be JSON summary.\n" + proc_write_large.stdout) from e

    run_id_write_large = summary_write_large.get("run_id")
    if not isinstance(run_id_write_large, str) or not run_id_write_large:
        raise SystemExit("Smoke test failed: write-too-large summary missing run_id.")

    dlq_after_write_large = set(dlq_dir.glob("*.json"))
    new_dlq_write_large = sorted(dlq_after_write_large - dlq_before_write_large, key=lambda p: p.name)
    if not new_dlq_write_large:
        raise SystemExit("Smoke test failed: write-too-large must create a DLQ record under dlq/.")
    latest_dlq_write_large = max(new_dlq_write_large, key=lambda p: p.stat().st_mtime)
    dlq_write_large = json.loads(latest_dlq_write_large.read_text(encoding="utf-8"))
    if dlq_write_large.get("stage") != "EXECUTION" or dlq_write_large.get("error_code") != "POLICY_VIOLATION":
        raise SystemExit("Smoke test failed: write-too-large DLQ must be EXECUTION/POLICY_VIOLATION.")

    if large_out_path.exists():
        raise SystemExit("Smoke test failed: fixtures/large_out.md must not be created on WRITE_TOO_LARGE.")

    evidence_write_large = out_dir_write_large / run_id_write_large
    mod_b_out_write_large = json.loads((evidence_write_large / "nodes" / "MOD_B" / "output.json").read_text(encoding="utf-8"))
    tc_write = mod_b_out_write_large.get("tool_calls") if isinstance(mod_b_out_write_large, dict) else None
    if not (
        isinstance(tc_write, list)
        and any(
            isinstance(tc, dict) and tc.get("tool") == "fs_write" and tc.get("error_code") == "WRITE_TOO_LARGE"
            for tc in tc_write
        )
    ):
        raise SystemExit("Smoke test failed: 0811 MOD_B tool_calls must include WRITE_TOO_LARGE.")

    # Keep one representative failure for the critical evidence snapshot.
    failure_run_id_for_snapshot = run_id_write_large
    failure_dlq_path_for_snapshot = latest_dlq_write_large
    failure_dlq_record_for_snapshot = dlq_write_large

    # Read too large should fail with POLICY_VIOLATION/READ_TOO_LARGE (MOD_A fs_read)
    huge_md = repo_root / "fixtures" / "huge.md"
    if not huge_md.exists():
        raise SystemExit("Smoke test failed: fixtures/huge.md missing (required for 0812_read_too_large).")
    if huge_md.stat().st_size <= 200_000:
        raise SystemExit("Smoke test failed: fixtures/huge.md must be > 200_000 bytes.")

    out_dir_read_large = smoke_root / "read_too_large"
    dlq_before_read_large = set(dlq_dir.glob("*.json"))
    proc_read_large = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0812_read_too_large.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_read_large),
        ],
        text=True,
        capture_output=True,
    )
    if proc_read_large.returncode == 0:
        raise SystemExit("Smoke test failed: read-too-large run must exit non-zero.")
    try:
        summary_read_large = json.loads(proc_read_large.stdout)
    except Exception as e:
        raise SystemExit("Smoke test failed: read-too-large stdout must be JSON summary.\n" + proc_read_large.stdout) from e

    run_id_read_large = summary_read_large.get("run_id")
    if not isinstance(run_id_read_large, str) or not run_id_read_large:
        raise SystemExit("Smoke test failed: read-too-large summary missing run_id.")

    dlq_after_read_large = set(dlq_dir.glob("*.json"))
    new_dlq_read_large = sorted(dlq_after_read_large - dlq_before_read_large, key=lambda p: p.name)
    if not new_dlq_read_large:
        raise SystemExit("Smoke test failed: read-too-large must create a DLQ record under dlq/.")
    latest_dlq_read_large = max(new_dlq_read_large, key=lambda p: p.stat().st_mtime)
    dlq_read_large = json.loads(latest_dlq_read_large.read_text(encoding="utf-8"))
    if dlq_read_large.get("stage") != "EXECUTION" or dlq_read_large.get("error_code") != "POLICY_VIOLATION":
        raise SystemExit("Smoke test failed: read-too-large DLQ must be EXECUTION/POLICY_VIOLATION.")

    evidence_read_large = out_dir_read_large / run_id_read_large
    mod_a_out_read_large = json.loads(
        (evidence_read_large / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8")
    )
    tc_read = mod_a_out_read_large.get("tool_calls") if isinstance(mod_a_out_read_large, dict) else None
    if not (
        isinstance(tc_read, list)
        and any(
            isinstance(tc, dict) and tc.get("tool") == "fs_read" and tc.get("error_code") == "READ_TOO_LARGE"
            for tc in tc_read
        )
    ):
        raise SystemExit("Smoke test failed: 0812 MOD_A tool_calls must include READ_TOO_LARGE.")

    # Budget gate tests (Sprint-5/02): tokens/time should fail deterministically with stage=BUDGET.
    fixture_0840 = repo_root / "fixtures" / "envelopes" / "0840_budget_tokens_exceeded.json"
    if not fixture_0840.exists():
        raise SystemExit("Smoke test failed: fixtures/envelopes/0840_budget_tokens_exceeded.json missing.")

    out_dir_budget_tokens = smoke_root / "budget_tokens"
    dlq_before_budget_tokens = set(dlq_dir.glob("*.json"))
    proc_budget_tokens = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(fixture_0840),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_budget_tokens),
        ],
        text=True,
        capture_output=True,
    )
    if proc_budget_tokens.returncode == 0:
        raise SystemExit("Smoke test failed: budget tokens exceeded run must exit non-zero.")
    try:
        summary_budget_tokens = json.loads(proc_budget_tokens.stdout)
    except Exception as e:
        raise SystemExit(
            "Smoke test failed: budget tokens exceeded stdout must be JSON summary.\n"
            + proc_budget_tokens.stdout
        ) from e
    if summary_budget_tokens.get("policy_violation_code") != "BUDGET_TOKENS_EXCEEDED":
        raise SystemExit(
            "Smoke test failed: expected policy_violation_code=BUDGET_TOKENS_EXCEEDED.\n"
            + json.dumps(summary_budget_tokens, indent=2, ensure_ascii=False)
        )
    run_id_budget_tokens = summary_budget_tokens.get("run_id")
    if not isinstance(run_id_budget_tokens, str) or not run_id_budget_tokens:
        raise SystemExit("Smoke test failed: budget tokens exceeded summary missing run_id.")

    dlq_after_budget_tokens = set(dlq_dir.glob("*.json"))
    new_budget_tokens_dlq = sorted(dlq_after_budget_tokens - dlq_before_budget_tokens, key=lambda p: p.name)
    if not new_budget_tokens_dlq:
        raise SystemExit("Smoke test failed: budget tokens exceeded must create a DLQ record under dlq/.")
    latest_budget_tokens_dlq = max(new_budget_tokens_dlq, key=lambda p: p.stat().st_mtime)
    dlq_budget_tokens = json.loads(latest_budget_tokens_dlq.read_text(encoding="utf-8"))
    if dlq_budget_tokens.get("stage") != "BUDGET":
        raise SystemExit("Smoke test failed: budget tokens exceeded DLQ stage must be BUDGET.")
    if dlq_budget_tokens.get("error_code") != "POLICY_VIOLATION":
        raise SystemExit("Smoke test failed: budget tokens exceeded DLQ error_code must be POLICY_VIOLATION.")

    evidence_budget_tokens = out_dir_budget_tokens / run_id_budget_tokens
    summary_file_budget_tokens = json.loads((evidence_budget_tokens / "summary.json").read_text(encoding="utf-8"))
    if summary_file_budget_tokens.get("budget_hit") != "TOKENS":
        raise SystemExit("Smoke test failed: budget tokens exceeded summary budget_hit must be TOKENS.")
    bt_spec = summary_file_budget_tokens.get("budget")
    bt_usage = summary_file_budget_tokens.get("budget_usage")
    if not isinstance(bt_spec, dict) or not isinstance(bt_usage, dict):
        raise SystemExit("Smoke test failed: budget tokens exceeded summary must include budget and budget_usage objects.")
    if int(bt_usage.get("est_tokens_used", 0)) <= int(bt_spec.get("max_tokens", 0)):
        raise SystemExit("Smoke test failed: expected est_tokens_used > max_tokens for BUDGET_TOKENS_EXCEEDED.")

    budget_tokens_dlq = latest_budget_tokens_dlq
    budget_tokens_summary = summary_file_budget_tokens

    fixture_0841 = repo_root / "fixtures" / "envelopes" / "0841_budget_time_exceeded.json"
    if not fixture_0841.exists():
        raise SystemExit("Smoke test failed: fixtures/envelopes/0841_budget_time_exceeded.json missing.")

    out_dir_budget_time = smoke_root / "budget_time"
    dlq_before_budget_time = set(dlq_dir.glob("*.json"))
    proc_budget_time = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(fixture_0841),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_budget_time),
        ],
        text=True,
        capture_output=True,
    )
    if proc_budget_time.returncode == 0:
        raise SystemExit("Smoke test failed: budget time exceeded run must exit non-zero.")
    try:
        summary_budget_time = json.loads(proc_budget_time.stdout)
    except Exception as e:
        raise SystemExit(
            "Smoke test failed: budget time exceeded stdout must be JSON summary.\n" + proc_budget_time.stdout
        ) from e
    if summary_budget_time.get("policy_violation_code") != "BUDGET_TIME_EXCEEDED":
        raise SystemExit(
            "Smoke test failed: expected policy_violation_code=BUDGET_TIME_EXCEEDED.\n"
            + json.dumps(summary_budget_time, indent=2, ensure_ascii=False)
        )
    run_id_budget_time = summary_budget_time.get("run_id")
    if not isinstance(run_id_budget_time, str) or not run_id_budget_time:
        raise SystemExit("Smoke test failed: budget time exceeded summary missing run_id.")

    dlq_after_budget_time = set(dlq_dir.glob("*.json"))
    new_budget_time_dlq = sorted(dlq_after_budget_time - dlq_before_budget_time, key=lambda p: p.name)
    if not new_budget_time_dlq:
        raise SystemExit("Smoke test failed: budget time exceeded must create a DLQ record under dlq/.")
    latest_budget_time_dlq = max(new_budget_time_dlq, key=lambda p: p.stat().st_mtime)
    dlq_budget_time = json.loads(latest_budget_time_dlq.read_text(encoding="utf-8"))
    if dlq_budget_time.get("stage") != "BUDGET":
        raise SystemExit("Smoke test failed: budget time exceeded DLQ stage must be BUDGET.")
    if dlq_budget_time.get("error_code") != "POLICY_VIOLATION":
        raise SystemExit("Smoke test failed: budget time exceeded DLQ error_code must be POLICY_VIOLATION.")

    evidence_budget_time = out_dir_budget_time / run_id_budget_time
    summary_file_budget_time = json.loads((evidence_budget_time / "summary.json").read_text(encoding="utf-8"))
    if summary_file_budget_time.get("budget_hit") != "TIME":
        raise SystemExit("Smoke test failed: budget time exceeded summary budget_hit must be TIME.")
    bt2_spec = summary_file_budget_time.get("budget")
    bt2_usage = summary_file_budget_time.get("budget_usage")
    if not isinstance(bt2_spec, dict) or not isinstance(bt2_usage, dict):
        raise SystemExit("Smoke test failed: budget time exceeded summary must include budget and budget_usage objects.")
    if int(bt2_usage.get("elapsed_ms", 0)) < int(bt2_spec.get("max_time_ms", 0)):
        raise SystemExit("Smoke test failed: expected elapsed_ms >= max_time_ms for BUDGET_TIME_EXCEEDED.")

    budget_time_dlq = latest_budget_time_dlq
    budget_time_summary = summary_file_budget_time

    out_dir_suspend = smoke_root / "suspend"

    proc_suspend = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0800_suspend.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_suspend),
        ]
    )
    summary_suspend = json.loads(proc_suspend.stdout)
    if summary_suspend.get("status") != "SUSPENDED":
        raise SystemExit(f"Smoke test failed: expected SUSPENDED, got: {summary_suspend.get('status')}")
    run_id_suspend = summary_suspend.get("run_id")
    if not isinstance(run_id_suspend, str) or not run_id_suspend:
        raise SystemExit("Smoke test failed: missing run_id for suspend run.")

    suspend_dir = out_dir_suspend / run_id_suspend
    suspend_summary = json.loads((suspend_dir / "summary.json").read_text(encoding="utf-8"))
    if suspend_summary.get("result_state") != "SUSPENDED":
        raise SystemExit("Smoke test failed: summary.json result_state must be SUSPENDED.")
    if not (suspend_dir / "suspend.json").exists():
        raise SystemExit("Smoke test failed: suspend.json must exist for suspended runs.")

    # Resume should require approval
    proc_resume_denied = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--resume",
            str(suspend_dir),
            "--approve",
            "false",
            "--workspace",
            str(repo_root),
        ],
        text=True,
        capture_output=True,
    )
    if proc_resume_denied.returncode == 0:
        raise SystemExit("Smoke test failed: resume without approval must exit non-zero.")
    if "APPROVAL_REQUIRED" not in (proc_resume_denied.stdout + proc_resume_denied.stderr):
        raise SystemExit("Smoke test failed: resume without approval must mention APPROVAL_REQUIRED.")

    # Resume with approval should complete and run MOD_B only
    proc_resume = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--resume",
            str(suspend_dir),
            "--approve",
            "true",
            "--workspace",
            str(repo_root),
        ]
    )
    resume_summary = json.loads(proc_resume.stdout)
    if resume_summary.get("result_state") != "COMPLETED":
        raise SystemExit(
            f"Smoke test failed: expected COMPLETED after resume, got: {resume_summary.get('result_state')}"
        )
    if resume_summary.get("resumed") is not True:
        raise SystemExit("Smoke test failed: resumed=true must be set in summary after resume.")
    if not (suspend_dir / "resume.log").exists():
        raise SystemExit("Smoke test failed: resume.log must be created on resume.")
    if not (suspend_dir / "nodes" / "MOD_B" / "output.json").exists():
        raise SystemExit("Smoke test failed: MOD_B evidence must exist after resume.")
    if out_file.exists():
        raise SystemExit("Smoke test failed: dry_run must not create fixtures/out.md (after resume).")

    # Optional: Resume should perform write only after approval (dry_run=false)
    out_dir_suspend_write = smoke_root / "suspend_write"

    resume_write_path = repo_root / "fixtures" / "resume_write.md"
    if resume_write_path.exists():
        resume_write_path.unlink()

    proc_suspend_write = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0801_suspend_write.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_suspend_write),
        ]
    )
    summary_suspend_write = json.loads(proc_suspend_write.stdout)
    if summary_suspend_write.get("status") != "SUSPENDED":
        raise SystemExit(
            f"Smoke test failed: expected SUSPENDED for 0801, got: {summary_suspend_write.get('status')}"
        )
    run_id_suspend_write = summary_suspend_write.get("run_id")
    if not isinstance(run_id_suspend_write, str) or not run_id_suspend_write:
        raise SystemExit("Smoke test failed: missing run_id for suspend-write run.")

    suspend_write_dir = out_dir_suspend_write / run_id_suspend_write
    if resume_write_path.exists():
        raise SystemExit("Smoke test failed: output file must not be written before resume approval.")

    proc_resume_write = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--resume",
            str(suspend_write_dir),
            "--approve",
            "true",
            "--workspace",
            str(repo_root),
        ]
    )
    resume_write_summary = json.loads(proc_resume_write.stdout)
    if resume_write_summary.get("result_state") != "COMPLETED":
        raise SystemExit("Smoke test failed: expected COMPLETED after resume approval (0801).")
    if not resume_write_path.exists():
        raise SystemExit("Smoke test failed: output file must be written after resume approval (0801).")
    mod_b_out = json.loads((suspend_write_dir / "nodes" / "MOD_B" / "output.json").read_text(encoding="utf-8"))
    if not (
        isinstance(mod_b_out, dict)
        and isinstance(mod_b_out.get("side_effects"), dict)
        and "wrote" in mod_b_out["side_effects"]
    ):
        raise SystemExit("Smoke test failed: expected MOD_B side_effects.wrote after resume approval (0801).")

    resume_write_path.unlink()

    # Governor v0.1 tests (quarantine, report_only override, concurrency cap)
    governor_path = repo_root / "governor" / "health_brain.v1.json"
    governor_path.parent.mkdir(parents=True, exist_ok=True)
    governor_original = governor_path.read_text(encoding="utf-8") if governor_path.exists() else None

    gov_quarantine_dlq: Path | None = None
    gov_concurrency_dlq: Path | None = None
    gov_report_only_run_id: str | None = None

    # 1) Quarantined intent should fail and write DLQ stage=GOVERNOR
    try:
        quarantine_cfg = {
            "version": "v1",
            "global_mode": "normal",
            "quarantine": {"intents": ["urn:core:summary:summary_to_file"], "workflows": []},
            "concurrency": {"max_parallel_runs": 1},
        }
        governor_path.write_text(json.dumps(quarantine_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        out_dir_quarantine = smoke_root / "gov_quarantine"
        dlq_before_q = set(dlq_dir.glob("*.json"))
        proc_quarantine = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(repo_root / "fixtures" / "envelopes" / "0830_quarantined_intent.json"),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_quarantine),
            ],
            text=True,
            capture_output=True,
        )
        if proc_quarantine.returncode == 0:
            raise SystemExit("Smoke test failed: quarantined intent run must exit non-zero.")

        dlq_after_q = set(dlq_dir.glob("*.json"))
        new_q = sorted(dlq_after_q - dlq_before_q, key=lambda p: p.name)
        if not new_q:
            raise SystemExit("Smoke test failed: quarantined intent must create a DLQ record under dlq/.")
        latest_q = max(new_q, key=lambda p: p.stat().st_mtime)
        dlq_q = json.loads(latest_q.read_text(encoding="utf-8"))
        if dlq_q.get("stage") != "GOVERNOR":
            raise SystemExit("Smoke test failed: quarantine DLQ stage must be GOVERNOR.")
        if dlq_q.get("error_code") != "POLICY_VIOLATION":
            raise SystemExit("Smoke test failed: quarantine DLQ error_code must be POLICY_VIOLATION.")
        if "QUARANTINED_INTENT" not in str(dlq_q.get("message", "")):
            raise SystemExit("Smoke test failed: quarantine DLQ message must mention QUARANTINED_INTENT.")

        gov_quarantine_dlq = latest_q
    finally:
        if governor_original is None:
            if governor_path.exists():
                governor_path.unlink()
        else:
            governor_path.write_text(governor_original, encoding="utf-8")

    # 2) report_only should suppress MOD_B writes even when dry_run=false and side_effect_policy allows
    try:
        report_only_cfg = {
            "version": "v1",
            "global_mode": "report_only",
            "quarantine": {"intents": [], "workflows": []},
            "concurrency": {"max_parallel_runs": 1},
        }
        governor_path.write_text(json.dumps(report_only_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        out_dir_report_only = smoke_root / "gov_report_only"
        if resume_write_path.exists():
            resume_write_path.unlink()

        proc_suspend_ro = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(repo_root / "fixtures" / "envelopes" / "0801_suspend_write.json"),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_report_only),
            ]
        )
        summary_suspend_ro = json.loads(proc_suspend_ro.stdout)
        if summary_suspend_ro.get("status") != "SUSPENDED":
            raise SystemExit("Smoke test failed: report_only 0801 must still SUSPEND at approval.")
        run_id_ro = summary_suspend_ro.get("run_id")
        if not isinstance(run_id_ro, str) or not run_id_ro:
            raise SystemExit("Smoke test failed: report_only suspend run missing run_id.")

        suspend_ro_dir = out_dir_report_only / run_id_ro
        proc_resume_ro = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--resume",
                str(suspend_ro_dir),
                "--approve",
                "true",
                "--workspace",
                str(repo_root),
            ]
        )
        resume_ro_summary = json.loads(proc_resume_ro.stdout)
        if resume_ro_summary.get("result_state") != "COMPLETED":
            raise SystemExit("Smoke test failed: report_only resume must complete.")

        if resume_write_path.exists():
            raise SystemExit("Smoke test failed: report_only must not write fixtures/resume_write.md after approval.")

        ro_summary_file = json.loads((suspend_ro_dir / "summary.json").read_text(encoding="utf-8"))
        if ro_summary_file.get("governor_mode_used") != "report_only":
            raise SystemExit("Smoke test failed: report_only summary must set governor_mode_used=report_only.")

        gov_report_only_run_id = run_id_ro
    finally:
        if governor_original is None:
            if governor_path.exists():
                governor_path.unlink()
        else:
            governor_path.write_text(governor_original, encoding="utf-8")

    # 3) Concurrency cap: if lock exists, run must fail with CONCURRENCY_LIMIT and DLQ stage=GOVERNOR
    governor_lock_path.parent.mkdir(parents=True, exist_ok=True)
    governor_lock_path.write_text("precreated lock\n", encoding="utf-8")
    try:
        dlq_before_c = set(dlq_dir.glob("*.json"))
        proc_conc = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(repo_root / "fixtures" / "envelopes" / "0001.json"),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_ok),
            ],
            text=True,
            capture_output=True,
        )
        if proc_conc.returncode == 0:
            raise SystemExit("Smoke test failed: concurrency-limited run must exit non-zero.")

        dlq_after_c = set(dlq_dir.glob("*.json"))
        new_c = sorted(dlq_after_c - dlq_before_c, key=lambda p: p.name)
        if not new_c:
            raise SystemExit("Smoke test failed: CONCURRENCY_LIMIT must create a DLQ record under dlq/.")
        latest_c = max(new_c, key=lambda p: p.stat().st_mtime)
        dlq_c = json.loads(latest_c.read_text(encoding="utf-8"))
        if dlq_c.get("stage") != "GOVERNOR":
            raise SystemExit("Smoke test failed: concurrency DLQ stage must be GOVERNOR.")
        if dlq_c.get("error_code") != "POLICY_VIOLATION":
            raise SystemExit("Smoke test failed: concurrency DLQ error_code must be POLICY_VIOLATION.")
        if "CONCURRENCY_LIMIT" not in str(dlq_c.get("message", "")):
            raise SystemExit("Smoke test failed: concurrency DLQ message must mention CONCURRENCY_LIMIT.")
        gov_concurrency_dlq = latest_c
    finally:
        if governor_lock_path.exists():
            governor_lock_path.unlink()

    # Confirm normal behavior after removing lock (idempotent hit is OK)
    proc_after_lock = run(
        [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(repo_root / "fixtures" / "envelopes" / "0001.json"),
            "--workspace",
            str(repo_root),
            "--out",
            str(out_dir_ok),
        ]
    )
    after_lock_summary = json.loads(proc_after_lock.stdout)
    if after_lock_summary.get("status") not in ("IDEMPOTENT_HIT", "COMPLETED", "SUSPENDED"):
        raise SystemExit("Smoke test failed: expected normal behavior after releasing governor lock.")

    # Tenant quota v0.1 tests (runs/day): run 2 ok, 3rd must fail with QUOTA_RUNS_EXCEEDED.
    if not quota_policy_path.exists():
        raise SystemExit("Smoke test failed: policies/policy_quota.v1.json missing.")

    quota_policy_original = quota_policy_repo or quota_policy_path.read_text(encoding="utf-8")
    quota_store_path = repo_root / ".cache" / "tenant_quota_store.v1.json"
    if quota_store_path.exists():
        quota_store_path.unlink()

    try:
        if quota_policy_overridden and quota_policy_repo is not None:
            quota_policy_path.write_text(quota_policy_repo, encoding="utf-8")
        strict_quota_policy = {
            "version": "v1",
            "default": {"max_runs_per_day": 2, "max_est_tokens_per_day": 8000},
            "overrides": {"TENANT-LOCAL": {"max_runs_per_day": 2, "max_est_tokens_per_day": 10000000}},
        }
        quota_policy_path.write_text(
            json.dumps(strict_quota_policy, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        out_dir_quota = smoke_root / "quota"

        proc_q1 = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(repo_root / "fixtures" / "envelopes" / "0850_quota_1.json"),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_quota),
            ]
        )
        sum_q1 = json.loads(proc_q1.stdout)
        if sum_q1.get("result_state") != "COMPLETED":
            raise SystemExit("Smoke test failed: 0850 quota run must complete.")

        proc_q2 = run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(repo_root / "fixtures" / "envelopes" / "0851_quota_2.json"),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_quota),
            ]
        )
        sum_q2 = json.loads(proc_q2.stdout)
        run_id_q2 = sum_q2.get("run_id")
        if sum_q2.get("result_state") != "COMPLETED":
            raise SystemExit("Smoke test failed: 0851 quota run must complete.")
        if not isinstance(run_id_q2, str) or not run_id_q2:
            raise SystemExit("Smoke test failed: 0851 quota run missing run_id.")

        quota_evidence_dir = out_dir_quota / run_id_q2
        q2_summary_file = json.loads((quota_evidence_dir / "summary.json").read_text(encoding="utf-8"))
        for k in ("quota", "quota_usage_before", "quota_usage_after", "quota_hit"):
            if k not in q2_summary_file:
                raise SystemExit(f"Smoke test failed: 0851 summary missing {k}.")
        if q2_summary_file.get("quota_hit") is not None:
            raise SystemExit("Smoke test failed: 0851 quota_hit must be null.")

        quota_pass_run_id = run_id_q2
        quota_pass_usage_after = q2_summary_file.get("quota_usage_after") if isinstance(q2_summary_file, dict) else None

        dlq_before_quota = set(dlq_dir.glob("*.json"))
        proc_q3 = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.orchestrator.local_runner",
                "--envelope",
                str(repo_root / "fixtures" / "envelopes" / "0852_quota_3.json"),
                "--workspace",
                str(repo_root),
                "--out",
                str(out_dir_quota),
            ],
            text=True,
            capture_output=True,
        )
        if proc_q3.returncode == 0:
            raise SystemExit("Smoke test failed: 0852 quota run must fail (runs/day exceeded).")
        try:
            sum_q3 = json.loads(proc_q3.stdout)
        except Exception as e:
            raise SystemExit("Smoke test failed: 0852 stdout must be JSON summary.\n" + proc_q3.stdout) from e
        if sum_q3.get("policy_violation_code") != "QUOTA_RUNS_EXCEEDED":
            raise SystemExit(
                "Smoke test failed: expected QUOTA_RUNS_EXCEEDED for 0852.\n"
                + json.dumps(sum_q3, indent=2, ensure_ascii=False)
            )
        quota_fail_code = sum_q3.get("policy_violation_code")

        dlq_after_quota = set(dlq_dir.glob("*.json"))
        new_quota_dlq = sorted(dlq_after_quota - dlq_before_quota, key=lambda p: p.name)
        if not new_quota_dlq:
            raise SystemExit("Smoke test failed: 0852 quota fail must create a DLQ record under dlq/.")
        latest_quota_dlq = max(new_quota_dlq, key=lambda p: p.stat().st_mtime)
        dlq_q = json.loads(latest_quota_dlq.read_text(encoding="utf-8"))
        if dlq_q.get("stage") != "QUOTA":
            raise SystemExit("Smoke test failed: quota DLQ stage must be QUOTA.")
        if dlq_q.get("error_code") != "POLICY_VIOLATION":
            raise SystemExit("Smoke test failed: quota DLQ error_code must be POLICY_VIOLATION.")
        if "QUOTA_RUNS_EXCEEDED" not in str(dlq_q.get("message", "")):
            raise SystemExit("Smoke test failed: quota DLQ message must mention QUOTA_RUNS_EXCEEDED.")
        quota_fail_dlq = latest_quota_dlq

        if not quota_store_path.exists():
            raise SystemExit("Smoke test failed: quota store file must be created at .cache/tenant_quota_store.v1.json.")
        store = json.loads(quota_store_path.read_text(encoding="utf-8"))
        from datetime import datetime, timezone

        date_key = datetime.now(timezone.utc).date().isoformat()
        day = store.get(date_key) if isinstance(store.get(date_key), dict) else {}
        tenant = day.get("TENANT-LOCAL") if isinstance(day.get("TENANT-LOCAL"), dict) else {}
        if int(tenant.get("runs_used", 0)) != 2:
            raise SystemExit("Smoke test failed: quota store TENANT-LOCAL runs_used must be 2 after 2 runs.")

        quota_store_date = date_key
        quota_store_tenant_snapshot = tenant
    finally:
        quota_policy_path.write_text(quota_policy_original, encoding="utf-8")
        if quota_store_path.exists():
            quota_store_path.unlink()

    if in_git and failure_run_id_for_snapshot and failure_dlq_path_for_snapshot and failure_dlq_record_for_snapshot:
        def _one_line_tool_call(run_dir: Path, node_id: str) -> str:
            p = run_dir / "nodes" / node_id / "output.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            calls = data.get("tool_calls") if isinstance(data, dict) else None
            first = calls[0] if isinstance(calls, list) and calls else {}
            if not isinstance(first, dict):
                first = {}
            tool = first.get("tool")
            status = first.get("status")
            bytes_in = first.get("bytes_in")
            bytes_out = first.get("bytes_out")
            err = first.get("error_code")
            return f"tool={tool} status={status} bytes_in={bytes_in} bytes_out={bytes_out} error_code={err}"

        def _summary_fields(run_dir: Path) -> str:
            s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            rs = s.get("result_state")
            th = s.get("threshold_used")
            prov = s.get("provider_used")
            fp = s.get("workflow_fingerprint")
            return f"result_state={rs} threshold_used={th} provider_used={prov} workflow_fingerprint={fp}"

        success_run_dir = evidence_dir
        failure_run_dir = out_dir_write_large / failure_run_id_for_snapshot

        print("CRITICAL_EVIDENCE_SUCCESS " + f"run_id={run_id} " + _summary_fields(success_run_dir))
        print("CRITICAL_EVIDENCE_SUCCESS first_tool_call " + _one_line_tool_call(success_run_dir, "MOD_A"))
        print("CRITICAL_EVIDENCE_FAILURE " + f"run_id={failure_run_id_for_snapshot} " + _summary_fields(failure_run_dir))
        print("CRITICAL_EVIDENCE_FAILURE first_tool_call " + _one_line_tool_call(failure_run_dir, "MOD_A"))
        print(
            "CRITICAL_EVIDENCE_FAILURE dlq "
            + f"file={failure_dlq_path_for_snapshot.name} "
            + f"stage={failure_dlq_record_for_snapshot.get('stage')} "
            + f"error_code={failure_dlq_record_for_snapshot.get('error_code')}"
        )

    if in_git and network_run_id_for_snapshot:
        run_dir = smoke_root / "network_policy" / network_run_id_for_snapshot
        s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        secrets_used = s.get("secrets_used") if isinstance(s, dict) else []
        secrets_used_list = secrets_used if isinstance(secrets_used, list) else []
        mod_a_out = json.loads((run_dir / "nodes" / "MOD_A" / "output.json").read_text(encoding="utf-8"))
        calls = mod_a_out.get("tool_calls") if isinstance(mod_a_out, dict) else None
        first_secrets = next(
            (tc for tc in calls if isinstance(tc, dict) and tc.get("tool") == "secrets_get"),
            None,
        ) if isinstance(calls, list) else None
        redacted = first_secrets.get("redacted") if isinstance(first_secrets, dict) else None
        print(
            "CRITICAL_EVIDENCE_SECRETS "
            + f"run_id={network_run_id_for_snapshot} "
            + f"secrets_used={secrets_used_list} "
            + f"first_redacted={redacted}"
        )

        if network_dlq_path_for_snapshot and isinstance(network_policy_violation_code_for_snapshot, str):
            print(
                "CRITICAL_EVIDENCE_NETWORK "
                + f"file={network_dlq_path_for_snapshot.name} "
                + f"policy_violation_code={network_policy_violation_code_for_snapshot}"
            )

    if gov_quarantine_dlq:
        dlq_q = json.loads(gov_quarantine_dlq.read_text(encoding="utf-8"))
        print(
            "CRITICAL_EVIDENCE_GOVERNOR_QUARANTINE "
            + f"file={gov_quarantine_dlq.name} "
            + f"reason={dlq_q.get('message')}"
        )

    if gov_report_only_run_id:
        run_dir = smoke_root / "gov_report_only" / gov_report_only_run_id
        s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        print(
            "CRITICAL_EVIDENCE_GOVERNOR_REPORT_ONLY "
            + f"run_id={gov_report_only_run_id} "
            + f"governor_mode_used={s.get('governor_mode_used')} "
            + "wrote_file=false"
        )

    if gov_concurrency_dlq:
        dlq_c = json.loads(gov_concurrency_dlq.read_text(encoding="utf-8"))
        print(
            "CRITICAL_EVIDENCE_GOVERNOR_CONCURRENCY "
            + f"file={gov_concurrency_dlq.name} "
            + f"reason={dlq_c.get('message')}"
        )

    if budget_tokens_dlq and isinstance(budget_tokens_summary, dict):
        bspec = budget_tokens_summary.get("budget") if isinstance(budget_tokens_summary.get("budget"), dict) else {}
        busage = (
            budget_tokens_summary.get("budget_usage")
            if isinstance(budget_tokens_summary.get("budget_usage"), dict)
            else {}
        )
        print(
            "CRITICAL_EVIDENCE_BUDGET_TOKENS "
            + f"file={budget_tokens_dlq.name} "
            + f"policy_violation_code={budget_tokens_summary.get('policy_violation_code')} "
            + f"est_tokens_used={busage.get('est_tokens_used')}/{bspec.get('max_tokens')}"
        )

    if budget_time_dlq and isinstance(budget_time_summary, dict):
        bspec = budget_time_summary.get("budget") if isinstance(budget_time_summary.get("budget"), dict) else {}
        busage = budget_time_summary.get("budget_usage") if isinstance(budget_time_summary.get("budget_usage"), dict) else {}
        print(
            "CRITICAL_EVIDENCE_BUDGET_TIME "
            + f"file={budget_time_dlq.name} "
            + f"elapsed_ms={busage.get('elapsed_ms')}/{bspec.get('max_time_ms')}"
        )

    if quota_pass_run_id and isinstance(quota_pass_usage_after, dict):
        print(
            "CRITICAL_EVIDENCE_QUOTA_PASS "
            + f"run_id={quota_pass_run_id} "
            + f"quota_usage_after={quota_pass_usage_after}"
        )

    if quota_fail_dlq and isinstance(quota_fail_code, str):
        print(
            "CRITICAL_EVIDENCE_QUOTA_FAIL "
            + f"file={quota_fail_dlq.name} "
            + f"policy_violation_code={quota_fail_code}"
        )

    if isinstance(quota_store_date, str) and isinstance(quota_store_tenant_snapshot, dict):
        runs_used = quota_store_tenant_snapshot.get("runs_used")
        est_tokens_used = quota_store_tenant_snapshot.get("est_tokens_used")
        print(
            "CRITICAL_QUOTA_STORE "
            + f"date={quota_store_date} "
            + "tenant=TENANT-LOCAL "
            + f"runs_used={runs_used} "
            + f"est_tokens_used={est_tokens_used}"
        )

    if isinstance(autonomy_promotion_snapshot_for_snapshot, dict):
        print(
            "CRITICAL_EVIDENCE_AUTONOMY_PROMOTION "
            + f"intent={autonomy_promotion_intent_for_snapshot} "
            + f"samples={autonomy_promotion_snapshot_for_snapshot.get('samples')} "
            + f"successes={autonomy_promotion_snapshot_for_snapshot.get('successes')} "
            + f"mode={autonomy_promotion_snapshot_for_snapshot.get('mode')}"
        )

    if isinstance(autonomy_used_run_id_for_snapshot, str):
        print(
            "CRITICAL_EVIDENCE_AUTONOMY_USED "
            + f"run_id={autonomy_used_run_id_for_snapshot} "
            + f"autonomy_mode_used={autonomy_used_mode_for_snapshot} "
            + f"autonomy_gate_triggered={autonomy_used_gate_for_snapshot}"
        )

    # Policy simulation v1: evidence history source (request.json) and union mode.
    sim_evidence_out = repo_root / "sim_report_evidence.json"
    if sim_evidence_out.exists():
        sim_evidence_out.unlink()
    proc_sim_evidence = run(
        [
            sys.executable,
            str(repo_root / "ci" / "policy_dry_run.py"),
            "--source",
            "evidence",
            "--evidence",
            str(repo_root / "evidence"),
            "--out",
            str(sim_evidence_out),
        ]
    )
    _ = proc_sim_evidence  # stdout captured by run(); avoid leaking full report here
    sim_evidence = json.loads(sim_evidence_out.read_text(encoding="utf-8"))
    if sim_evidence.get("source") != "evidence":
        raise SystemExit("Smoke test failed: sim_report_evidence.json source must be evidence.")
    if "threshold_used" not in sim_evidence:
        raise SystemExit("Smoke test failed: sim_report_evidence.json missing threshold_used.")
    total_inputs_ev = sim_evidence.get("total_inputs")
    if not isinstance(total_inputs_ev, int) or total_inputs_ev < 1:
        raise SystemExit("Smoke test failed: sim_report_evidence.json total_inputs must be >= 1.")
    breakdown_ev = sim_evidence.get("inputs_breakdown")
    if not isinstance(breakdown_ev, dict) or int(breakdown_ev.get("evidence", 0)) < 1:
        raise SystemExit("Smoke test failed: sim_report_evidence.json inputs_breakdown.evidence must be >= 1.")

    sim_both_out = repo_root / "sim_report_both.json"
    if sim_both_out.exists():
        sim_both_out.unlink()
    proc_sim_both = run(
        [
            sys.executable,
            str(repo_root / "ci" / "policy_dry_run.py"),
            "--source",
            "both",
            "--fixtures",
            str(repo_root / "fixtures" / "envelopes"),
            "--evidence",
            str(repo_root / "evidence"),
            "--out",
            str(sim_both_out),
        ]
    )
    _ = proc_sim_both
    sim_both = json.loads(sim_both_out.read_text(encoding="utf-8"))
    if sim_both.get("source") != "both":
        raise SystemExit("Smoke test failed: sim_report_both.json source must be both.")
    total_inputs_both = sim_both.get("total_inputs")
    if not isinstance(total_inputs_both, int) or total_inputs_both < 1:
        raise SystemExit("Smoke test failed: sim_report_both.json total_inputs must be >= 1.")
    breakdown_both = sim_both.get("inputs_breakdown")
    if not isinstance(breakdown_both, dict):
        raise SystemExit("Smoke test failed: sim_report_both.json inputs_breakdown must be an object.")
    fixtures_n = int(breakdown_both.get("fixtures", 0))
    evidence_n = int(breakdown_both.get("evidence", 0))
    if total_inputs_both > fixtures_n + evidence_n:
        raise SystemExit("Smoke test failed: sim_report_both.json total_inputs exceeds scanned inputs (dedupe bug).")
    # Note: total_inputs_both can be < max(fixtures_n, evidence_n) because evidence history may contain duplicates
    # (e.g., multiple runs of the same request_id/idempotency key).

    counts_ev = sim_evidence.get("counts") if isinstance(sim_evidence.get("counts"), dict) else {}
    counts_both = sim_both.get("counts") if isinstance(sim_both.get("counts"), dict) else {}
    print(
        "CRITICAL_POLICY_SIM_EVIDENCE "
        + f"total_inputs={total_inputs_ev} "
        + f"counts={counts_ev}"
    )
    print(
        "CRITICAL_POLICY_SIM_BOTH "
        + f"inputs_breakdown={breakdown_both} "
        + f"counts={counts_both}"
    )

    # Policy simulation v2: baseline vs candidate diff report.
    # Self-check: baseline=HEAD, candidate=working tree => diff must be zero in clean checkouts.
    if in_git:
        if not is_git_clean_work_tree(repo_root):
            print("CRITICAL_POLICY_DIFF SKIPPED reason=dirty_worktree")
        else:
            policy_diff_out = repo_root / ".cache" / "policy_diff_self.json"
            policy_diff_out.parent.mkdir(parents=True, exist_ok=True)
            if policy_diff_out.exists():
                policy_diff_out.unlink()

            run(
                [
                    sys.executable,
                    str(repo_root / "ci" / "policy_diff_sim.py"),
                    "--source",
                    "both",
                    "--fixtures",
                    str(repo_root / "fixtures" / "envelopes"),
                    "--evidence",
                    str(repo_root / "evidence"),
                    "--baseline",
                    "HEAD",
                    "--out",
                    str(policy_diff_out),
                ]
            )

            diff_report = json.loads(policy_diff_out.read_text(encoding="utf-8"))
            if diff_report.get("baseline_available") is not True:
                raise SystemExit("Smoke test failed: policy_diff_sim baseline=HEAD must be available in git.")

            diff_counts = diff_report.get("diff_counts")
            if not isinstance(diff_counts, dict):
                raise SystemExit("Smoke test failed: policy_diff_sim diff_counts must be an object.")

            nonzero = {}
            for k, v in diff_counts.items():
                try:
                    iv = int(v)
                except Exception:
                    continue
                if iv != 0:
                    nonzero[k] = iv
            if nonzero:
                raise SystemExit(
                    "Smoke test failed: policy_diff_sim self-check expected zero diff_counts, got: "
                    + json.dumps(nonzero, sort_keys=True)
                )

            inputs_total = diff_report.get("inputs_total")
            if not isinstance(inputs_total, int) or inputs_total < 0:
                raise SystemExit("Smoke test failed: policy_diff_sim inputs_total must be an int >= 0.")

            print(f"CRITICAL_POLICY_DIFF inputs_total={inputs_total} nonzero_changes=0")
    else:
        print("CRITICAL_POLICY_DIFF SKIPPED reason=no_git")

    # Supply chain v0.1: SBOM + signing stub + verification.
    # - For local smoke we allow a deterministic DEV_KEY fallback.
    # - CI enforcement (real key required) is handled by a dedicated gate step.
    sc_env = os.environ.copy()
    if not sc_env.get("SUPPLY_CHAIN_SIGNING_KEY"):
        sc_env["SUPPLY_CHAIN_SIGNING_KEY"] = "DEV_KEY"

    sbom_proc = subprocess.run(
        [sys.executable, str(repo_root / "supply_chain" / "sbom.py")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
        check=True,
    )
    _ = sbom_proc

    sign_proc = subprocess.run(
        [sys.executable, str(repo_root / "supply_chain" / "sign.py")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
        check=True,
    )
    _ = sign_proc

    verify_proc = subprocess.run(
        [sys.executable, str(repo_root / "supply_chain" / "verify.py")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if verify_proc.returncode != 0:
        raise SystemExit(
            "Smoke test failed: supply_chain verify failed:\n"
            + (verify_proc.stdout or "").strip()
            + ("\n" + (verify_proc.stderr or "").strip() if (verify_proc.stderr or "").strip() else "")
        )

    try:
        verify_status = json.loads((verify_proc.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: verify.py did not output valid JSON: " + str(e))
    if verify_status.get("status") != "OK":
        raise SystemExit("Smoke test failed: verify.py status must be OK.")

    sbom_path = repo_root / "supply_chain" / "sbom.v1.json"
    sig_path = repo_root / "supply_chain" / "signature.v1.json"
    if not sbom_path.exists():
        raise SystemExit("Smoke test failed: missing supply_chain/sbom.v1.json")
    if not sig_path.exists():
        raise SystemExit("Smoke test failed: missing supply_chain/signature.v1.json")

    sbom_obj = json.loads(sbom_path.read_text(encoding="utf-8"))
    if not isinstance(sbom_obj, dict):
        raise SystemExit("Smoke test failed: sbom.v1.json must be a JSON object.")
    sbom_project = sbom_obj.get("project") if isinstance(sbom_obj.get("project"), dict) else None
    if not isinstance(sbom_project, dict):
        raise SystemExit("Smoke test failed: sbom.v1.json missing project object.")
    sbom_proj_name = sbom_project.get("name")
    sbom_proj_version = sbom_project.get("version")
    if not isinstance(sbom_proj_name, str) or not sbom_proj_name:
        raise SystemExit("Smoke test failed: sbom project.name must be a non-empty string.")
    if not isinstance(sbom_proj_version, str) or not sbom_proj_version:
        raise SystemExit("Smoke test failed: sbom project.version must be a non-empty string.")

    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        raise SystemExit("Smoke test failed: missing pyproject.toml for version stamp check.")
    with pyproject_path.open("rb") as f:
        py_obj = tomllib.load(f)
    py_proj = py_obj.get("project") if isinstance(py_obj.get("project"), dict) else {}
    expected_name = py_proj.get("name") if isinstance(py_proj.get("name"), str) else ""
    expected_version = py_proj.get("version") if isinstance(py_proj.get("version"), str) else ""
    if expected_name and sbom_proj_name != expected_name:
        raise SystemExit("Smoke test failed: sbom project.name does not match pyproject.toml.")
    if expected_version and sbom_proj_version != expected_version:
        raise SystemExit("Smoke test failed: sbom project.version does not match pyproject.toml.")

    print(f"CRITICAL_RELEASE_VERSION: version={sbom_proj_version}")

    sbom_hash = sha256(sbom_path.read_bytes()).hexdigest()
    sig_obj = json.loads(sig_path.read_text(encoding="utf-8"))
    sig_hex = sig_obj.get("signature") if isinstance(sig_obj, dict) else None
    sig_prefix = sig_hex[:12] if isinstance(sig_hex, str) and sig_hex else "unknown"
    print(
        "CRITICAL_SUPPLY_CHAIN "
        + f"sbom_hash={sbom_hash} "
        + f"signature_prefix={sig_prefix} "
        + "verify_ok=true"
    )

    license_proc = subprocess.run(
        [sys.executable, str(repo_root / "supply_chain" / "license_gate.py")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if license_proc.returncode != 0:
        raise SystemExit(
            "Smoke test failed: license gate failed:\n"
            + (license_proc.stdout or "").strip()
            + ("\n" + (license_proc.stderr or "").strip() if (license_proc.stderr or "").strip() else "")
        )
    try:
        license_status = json.loads((license_proc.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: license_gate.py did not output valid JSON: " + str(e))
    if license_status.get("status") != "OK":
        raise SystemExit("Smoke test failed: license gate status must be OK.")

    dep_count = license_status.get("dependency_count")
    if not isinstance(dep_count, int) or dep_count < 1:
        raise SystemExit("Smoke test failed: license gate dependency_count must be >= 1.")

    print("CRITICAL_SUPPLY_LICENSE " + f"dependency_count={dep_count} " + "status=OK")

    cve_proc = subprocess.run(
        [sys.executable, str(repo_root / "supply_chain" / "cve_gate.py")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if cve_proc.returncode != 0:
        raise SystemExit(
            "Smoke test failed: CVE gate failed:\n"
            + (cve_proc.stdout or "").strip()
            + ("\n" + (cve_proc.stderr or "").strip() if (cve_proc.stderr or "").strip() else "")
        )

    try:
        cve_status = json.loads((cve_proc.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: cve_gate.py did not output valid JSON: " + str(e))

    if cve_status.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: CVE gate status must be OK or WARN.")

    checked = cve_status.get("checked_deps")
    unknown = cve_status.get("unknown_deps")
    checked_n = len(checked) if isinstance(checked, list) else 0
    unknown_n = len(unknown) if isinstance(unknown, list) else 0

    if checked_n < 1:
        raise SystemExit("Smoke test failed: CVE gate checked_deps must be a non-empty list.")

    print(
        "CRITICAL_SUPPLY_CVE "
        + f"checked_deps={checked_n} "
        + f"unknown_deps={unknown_n} "
        + f"status={cve_status.get('status')}"
    )

    # Evidence integrity v1: manifest + verify-on-read + tamper test (restore after).
    integrity_manifest = evidence_dir_ok / "integrity.manifest.v1.json"
    if not integrity_manifest.exists():
        raise SystemExit("Smoke test failed: missing integrity manifest for 0001 run: " + str(integrity_manifest))

    verify_ok_proc = subprocess.run(
        [sys.executable, "-m", "src.evidence.integrity_verify", "--run", str(evidence_dir_ok)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if verify_ok_proc.returncode != 0:
        raise SystemExit(
            "Smoke test failed: integrity verify must return OK for 0001 run:\n"
            + (verify_ok_proc.stdout or "").strip()
            + ("\n" + (verify_ok_proc.stderr or "").strip() if (verify_ok_proc.stderr or "").strip() else "")
        )
    try:
        integrity_ok = json.loads((verify_ok_proc.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: integrity verify did not output valid JSON: " + str(e))
    if integrity_ok.get("status") != "OK":
        raise SystemExit("Smoke test failed: integrity verify status must be OK for 0001 run.")

    print("CRITICAL_EVIDENCE_INTEGRITY_OK: " + run_id_ok)

    summary_ok_path = evidence_dir_ok / "summary.json"
    original_summary_bytes = summary_ok_path.read_bytes()
    try:
        tampered = bytearray(original_summary_bytes)
        if not tampered:
            raise SystemExit("Smoke test failed: cannot tamper empty summary.json")
        tampered[0] = ord("[") if tampered[0] != ord("[") else ord("{")
        summary_ok_path.write_bytes(bytes(tampered))

        verify_bad_proc = subprocess.run(
            [sys.executable, "-m", "src.evidence.integrity_verify", "--run", str(evidence_dir_ok)],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if verify_bad_proc.returncode != 3:
            raise SystemExit(
                "Smoke test failed: integrity verify must return exit code 3 for tampered evidence.\n"
                + (verify_bad_proc.stdout or "").strip()
                + ("\n" + (verify_bad_proc.stderr or "").strip() if (verify_bad_proc.stderr or "").strip() else "")
            )
        try:
            integrity_bad = json.loads((verify_bad_proc.stdout or "").strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: integrity verify (tamper) did not output valid JSON: " + str(e))
        if integrity_bad.get("status") != "MISMATCH":
            raise SystemExit("Smoke test failed: tampered evidence must produce status=MISMATCH.")

        print("CRITICAL_EVIDENCE_INTEGRITY_TAMPER: " + run_id_ok + " status=" + str(integrity_bad.get("status")))
    finally:
        summary_ok_path.write_bytes(original_summary_bytes)

    # Evidence export v0.1: zip export with integrity precheck (and force override).
    export_dir = repo_root / ".cache" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    export_zip_ok = export_dir / f"{run_id_ok}.zip"
    if export_zip_ok.exists():
        export_zip_ok.unlink()

    proc_export_ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.manage",
            "evidence-export",
            "--run",
            str(evidence_dir_ok.relative_to(repo_root)),
            "--out",
            str(export_zip_ok.relative_to(repo_root)),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_export_ok.returncode != 0:
        raise SystemExit(
            "Smoke test failed: evidence-export must succeed for untampered run.\n"
            + (proc_export_ok.stdout or "").strip()
            + ("\n" + (proc_export_ok.stderr or "").strip() if (proc_export_ok.stderr or "").strip() else "")
        )

    if not export_zip_ok.exists():
        raise SystemExit("Smoke test failed: evidence-export did not create zip: " + str(export_zip_ok))

    with zipfile.ZipFile(export_zip_ok, "r") as zf:
        names = set(zf.namelist())
        required = {
            "summary.json",
            "request.json",
            "provenance.v1.json",
            "integrity.manifest.v1.json",
            "EXPORT_README.txt",
        }
        missing = sorted(required - names)
        if missing:
            raise SystemExit("Smoke test failed: evidence-export zip missing: " + ", ".join(missing))

    zip_bytes_ok = int(export_zip_ok.stat().st_size)
    if zip_bytes_ok < 1:
        raise SystemExit("Smoke test failed: evidence-export zip_bytes must be > 0.")
    print(f"CRITICAL_EVIDENCE_EXPORT_OK: run_id={run_id_ok} zip_bytes={zip_bytes_ok}")

    tampered_root = repo_root / ".cache" / "evidence_tampered" / run_id_ok
    if tampered_root.exists():
        rmtree(tampered_root)
    tampered_root.parent.mkdir(parents=True, exist_ok=True)
    copytree(evidence_dir_ok, tampered_root)

    tampered_summary = tampered_root / "summary.json"
    tb = tampered_summary.read_bytes()
    if tb.endswith(b"\n"):
        tampered_summary.write_bytes(tb[:-1] + b" \n")
    else:
        tampered_summary.write_bytes(tb + b" ")

    export_zip_tampered = export_dir / f"{run_id_ok}.tampered.zip"
    if export_zip_tampered.exists():
        export_zip_tampered.unlink()

    proc_export_tampered = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.manage",
            "evidence-export",
            "--run",
            str(tampered_root.relative_to(repo_root)),
            "--out",
            str(export_zip_tampered.relative_to(repo_root)),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_export_tampered.returncode == 0:
        raise SystemExit("Smoke test failed: tampered evidence-export must fail without --force.")

    try:
        export_fail_obj = json.loads((proc_export_tampered.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: evidence-export failure must output JSON.") from e

    if export_fail_obj.get("reason") != "INTEGRITY_MISMATCH":
        raise SystemExit(
            "Smoke test failed: tampered evidence-export must fail with reason=INTEGRITY_MISMATCH.\n"
            + json.dumps(export_fail_obj, indent=2, ensure_ascii=False)
        )

    export_zip_forced = export_dir / f"{run_id_ok}.tampered.forced.zip"
    if export_zip_forced.exists():
        export_zip_forced.unlink()

    proc_export_forced = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.manage",
            "evidence-export",
            "--run",
            str(tampered_root.relative_to(repo_root)),
            "--out",
            str(export_zip_forced.relative_to(repo_root)),
            "--force",
            "true",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_export_forced.returncode != 0:
        raise SystemExit(
            "Smoke test failed: tampered evidence-export must succeed with --force true.\n"
            + (proc_export_forced.stdout or "").strip()
            + ("\n" + (proc_export_forced.stderr or "").strip() if (proc_export_forced.stderr or "").strip() else "")
        )

    if not export_zip_forced.exists():
        raise SystemExit("Smoke test failed: forced evidence-export did not create zip: " + str(export_zip_forced))

    with zipfile.ZipFile(export_zip_forced, "r") as zf:
        readme_raw = zf.read("EXPORT_README.txt")
        readme_text = readme_raw.decode("utf-8", errors="replace")
        if "integrity_status: OK" in readme_text:
            raise SystemExit("Smoke test failed: forced export README must indicate integrity is not OK.")
        if "integrity_status: MISMATCH" not in readme_text:
            raise SystemExit("Smoke test failed: forced export README must include integrity_status: MISMATCH.")

    print("CRITICAL_EVIDENCE_EXPORT_TAMPER: forced=true")
    rmtree(tampered_root.parent)

    # GC/Reaper v0.1: retention policy + dry-run + delete (deterministic via --now).
    old_run_dir = repo_root / "evidence" / "__old_test_run"
    if old_run_dir.exists():
        rmtree(old_run_dir)
    old_run_dir.mkdir(parents=True, exist_ok=True)

    old_request = {
        "request_id": "REQ-OLD",
        "tenant_id": "TENANT-LOCAL",
        "intent": "urn:core:summary:summary_to_file",
        "risk_score": 0.0,
        "dry_run": True,
        "side_effect_policy": "none",
    }
    (old_run_dir / "request.json").write_text(
        json.dumps(old_request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    old_summary = {
        "run_id": "__old_test_run",
        "request_id": "REQ-OLD",
        "tenant_id": "TENANT-LOCAL",
        "workflow_id": "WF_CORE",
        "result_state": "COMPLETED",
        "started_at": "2000-01-01T00:00:00Z",
        "finished_at": "2000-01-01T00:00:00Z",
    }
    (old_run_dir / "summary.json").write_text(
        json.dumps(old_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    old_req_hash = sha256((old_run_dir / "request.json").read_bytes()).hexdigest()
    old_sum_hash = sha256((old_run_dir / "summary.json").read_bytes()).hexdigest()
    old_manifest = {
        "version": "v1",
        "run_id": "__old_test_run",
        "created_at": "2000-01-01T00:00:00Z",
        "files": [
            {"path": "request.json", "sha256": old_req_hash},
            {"path": "summary.json", "sha256": old_sum_hash},
        ],
    }
    (old_run_dir / "integrity.manifest.v1.json").write_text(
        json.dumps(old_manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )

    old_dlq = repo_root / "dlq" / "20000101_000000_REQ-OLD.json"
    if old_dlq.exists():
        old_dlq.unlink()
    old_dlq.write_text(
        json.dumps(
            {
                "stage": "TEST",
                "error_code": "OLD",
                "message": "Synthetic old DLQ record for smoke GC test.",
                "envelope": {"request_id": "REQ-OLD", "tenant_id": "TENANT-LOCAL", "intent": "urn:core:summary:summary_to_file"},
                "ts": "2000-01-01T00:00:00Z",
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    reaper_report = repo_root / "reaper_report.json"
    if reaper_report.exists():
        reaper_report.unlink()
    reaper_delete_report = repo_root / "reaper_report_delete.json"
    if reaper_delete_report.exists():
        reaper_delete_report.unlink()

    proc_reaper_dry = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.reaper",
            "--dry-run",
            "true",
            "--now",
            "2001-01-01T00:00:00Z",
            "--out",
            str(reaper_report),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_reaper_dry.returncode != 0:
        raise SystemExit("Smoke test failed: reaper dry-run failed:\n" + (proc_reaper_dry.stderr or proc_reaper_dry.stdout or ""))

    report_dry = json.loads(reaper_report.read_text(encoding="utf-8"))
    evidence_dry = report_dry.get("evidence") if isinstance(report_dry.get("evidence"), dict) else {}
    dlq_dry = report_dry.get("dlq") if isinstance(report_dry.get("dlq"), dict) else {}

    old_ev_rel = "evidence/__old_test_run"
    old_dlq_rel = "dlq/20000101_000000_REQ-OLD.json"
    if old_ev_rel not in (evidence_dry.get("paths") or []):
        raise SystemExit("Smoke test failed: reaper dry-run must include old evidence run.")
    if old_dlq_rel not in (dlq_dry.get("paths") or []):
        raise SystemExit("Smoke test failed: reaper dry-run must include old dlq record.")

    print(
        "CRITICAL_REAPER_DRYRUN: "
        + f"evidence_candidates={int(evidence_dry.get('candidates', 0))} "
        + f"dlq_candidates={int(dlq_dry.get('candidates', 0))}"
    )

    proc_reaper_del = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.reaper",
            "--dry-run",
            "false",
            "--now",
            "2001-01-01T00:00:00Z",
            "--out",
            str(reaper_delete_report),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_reaper_del.returncode != 0:
        raise SystemExit("Smoke test failed: reaper delete failed:\n" + (proc_reaper_del.stderr or proc_reaper_del.stdout or ""))

    if old_run_dir.exists():
        raise SystemExit("Smoke test failed: reaper delete must remove old evidence run directory.")
    if old_dlq.exists():
        raise SystemExit("Smoke test failed: reaper delete must remove old DLQ record.")
    if not (repo_root / "dlq" / ".gitkeep").exists():
        raise SystemExit("Smoke test failed: reaper must not delete dlq/.gitkeep")

    report_del = json.loads(reaper_delete_report.read_text(encoding="utf-8"))
    evidence_del = report_del.get("evidence") if isinstance(report_del.get("evidence"), dict) else {}
    dlq_del = report_del.get("dlq") if isinstance(report_del.get("dlq"), dict) else {}

    print(
        "CRITICAL_REAPER_DELETE: "
        + f"evidence_deleted={int(evidence_del.get('deleted', 0))} "
        + f"dlq_deleted={int(dlq_del.get('deleted', 0))}"
    )

    # Keep repo clean: remove reports after assertions.
    if reaper_report.exists():
        reaper_report.unlink()
    if reaper_delete_report.exists():
        reaper_delete_report.unlink()

    # Module kit v0.1: templates + generator (no execution wiring).
    module_gen_dir = repo_root / ".cache" / "module_gen_test"
    if module_gen_dir.exists():
        rmtree(module_gen_dir)
    module_gen_dir.parent.mkdir(parents=True, exist_ok=True)

    proc_modgen = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.tools.module_gen",
            "--module-id",
            "MOD_SMOKE_EXAMPLE",
            "--intent",
            "urn:core:example:smoke",
            "--outdir",
            str(module_gen_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_modgen.returncode != 0:
        raise SystemExit(
            "Smoke test failed: module_gen failed:\n"
            + (proc_modgen.stderr or proc_modgen.stdout or "")
        )

    expected_kit_files = [
        "registry_entry.json",
        "node_input.schema.json",
        "node_output.schema.json",
        "fixture_envelope.json",
        "README.md",
        "REGISTRY_PATCH.txt",
    ]
    for rel in expected_kit_files:
        if not (module_gen_dir / rel).exists():
            raise SystemExit("Smoke test failed: module kit missing file: " + rel)

    for rel in expected_kit_files:
        text = (module_gen_dir / rel).read_text(encoding="utf-8")
        if "{{MODULE_ID}}" in text or "{{INTENT}}" in text:
            raise SystemExit("Smoke test failed: module kit placeholders not resolved in: " + rel)

    if "MOD_SMOKE_EXAMPLE" not in (module_gen_dir / "registry_entry.json").read_text(encoding="utf-8"):
        raise SystemExit("Smoke test failed: module kit registry_entry.json missing module id.")
    if "urn:core:example:smoke" not in (module_gen_dir / "fixture_envelope.json").read_text(encoding="utf-8"):
        raise SystemExit("Smoke test failed: module kit fixture_envelope.json missing intent.")

    print("CRITICAL_MODULE_KIT: generated=true")
    rmtree(module_gen_dir)

    # Policy apply CLI v0.1: validate + dry-run + diff (optional) + supply-chain.
    policy_check_dir = repo_root / ".cache" / "policy_check"
    if policy_check_dir.exists():
        rmtree(policy_check_dir)

    proc_policy_check = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.manage",
            "policy-check",
            "--source",
            "fixtures",
            "--max-deprecation-warnings",
            "1",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_policy_check.returncode != 0:
        raise SystemExit(
            "Smoke test failed: ops manage policy-check failed:\n"
            + (proc_policy_check.stderr or proc_policy_check.stdout or "")
        )

    policy_check_summary_line = ""
    for line in reversed((proc_policy_check.stdout or "").splitlines()):
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            policy_check_summary_line = stripped
            break
    if not policy_check_summary_line:
        raise SystemExit("Smoke test failed: policy-check must print JSON summary line.")
    try:
        policy_check_summary = json.loads(policy_check_summary_line)
    except Exception as e:
        raise SystemExit("Smoke test failed: policy-check summary line is not valid JSON.") from e
    if not isinstance(policy_check_summary, dict):
        raise SystemExit("Smoke test failed: policy-check summary must be a JSON object.")
    if "deprecation_warning_count" not in policy_check_summary:
        raise SystemExit("Smoke test failed: policy-check summary missing deprecation_warning_count.")
    dep_count_pc = int(policy_check_summary.get("deprecation_warning_count", -1))
    if dep_count_pc < 0:
        raise SystemExit("Smoke test failed: invalid deprecation_warning_count in policy-check summary.")
    if dep_count_pc > 1:
        raise SystemExit("Smoke test failed: deprecation_warning_count exceeds threshold (1).")

    sim_report_pc = policy_check_dir / "sim_report.json"
    diff_report_pc = policy_check_dir / "policy_diff_report.json"
    report_md_pc = policy_check_dir / "POLICY_REPORT.md"
    if not sim_report_pc.exists():
        raise SystemExit("Smoke test failed: policy-check must create .cache/policy_check/sim_report.json")
    if not diff_report_pc.exists():
        raise SystemExit("Smoke test failed: policy-check must create .cache/policy_check/policy_diff_report.json")
    if not report_md_pc.exists():
        raise SystemExit("Smoke test failed: policy-check must create .cache/policy_check/POLICY_REPORT.md")

    sim_pc = json.loads(sim_report_pc.read_text(encoding="utf-8"))
    counts_pc = sim_pc.get("counts") if isinstance(sim_pc, dict) else None
    if not isinstance(counts_pc, dict):
        raise SystemExit("Smoke test failed: policy-check sim_report.json missing counts.")

    allow_pc = int(counts_pc.get("allow", 0))
    suspend_pc = int(counts_pc.get("suspend", 0))
    block_pc = int(counts_pc.get("block_unknown_intent", 0))
    invalid_pc = int(counts_pc.get("invalid_envelope", 0))

    diff_pc = json.loads(diff_report_pc.read_text(encoding="utf-8"))
    if isinstance(diff_pc, dict) and diff_pc.get("status") == "SKIPPED":
        diff_status_pc = "SKIPPED"
        diff_nonzero_pc = 0
    else:
        diff_counts_pc = diff_pc.get("diff_counts") if isinstance(diff_pc, dict) else None
        if isinstance(diff_counts_pc, dict):
            diff_status_pc = "OK"
            diff_nonzero_pc = sum(int(v) for v in diff_counts_pc.values() if isinstance(v, int) and v > 0)
        else:
            diff_status_pc = "OK"
            diff_nonzero_pc = 0

    print("CRITICAL_POLICY_CHECK: ok=true outdir=.cache/policy_check")
    print(
        "CRITICAL_POLICY_CHECK_SIM "
        + f"allow={allow_pc} "
        + f"suspend={suspend_pc} "
        + f"block={block_pc} "
        + f"invalid={invalid_pc}"
    )
    print(f"CRITICAL_POLICY_CHECK_DIFF nonzero={diff_nonzero_pc} status={diff_status_pc}")
    print(f"CRITICAL_POLICY_CHECK_DEPRECATION warnings={dep_count_pc} max=1")

    md_text = report_md_pc.read_text(encoding="utf-8")
    for heading in ("Deprecation warnings", "Dry-run summary", "Diff summary", "Side-effects status", "Supply chain summary"):
        if heading not in md_text:
            raise SystemExit("Smoke test failed: POLICY_REPORT.md missing heading: " + heading)
    print("CRITICAL_POLICY_REPORT: generated=true")

    # Integration-only OpenAI ping: must fail safely when network is disabled (no secrets, no network).
    policy_security_path = repo_root / "policies" / "policy_security.v1.json"
    original_policy_security_ping = policy_security_path.read_text(encoding="utf-8") if policy_security_path.exists() else None
    if original_policy_security_ping is not None:
        try:
            sec_obj = json.loads(original_policy_security_ping)
            if not isinstance(sec_obj, dict):
                raise TypeError("policy_security.v1.json not an object")
            sec_obj["network_access"] = False
            sec_obj["network_allowlist"] = []
            policy_security_path.write_text(
                json.dumps(sec_obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            proc_ping = subprocess.run(
                [sys.executable, "-m", "src.ops.manage", "openai-ping", "--timeout-ms", "1000"],
                cwd=repo_root,
                text=True,
                capture_output=True,
                env=sc_env,
            )
            # Either exit non-zero OR status FAIL is acceptable. We enforce a deterministic failure code here.
            try:
                ping_obj = json.loads((proc_ping.stdout or "").strip() or "{}")
            except Exception as e:
                raise SystemExit("Smoke test failed: openai-ping must output JSON.\n" + proc_ping.stdout) from e
            if not isinstance(ping_obj, dict):
                raise SystemExit("Smoke test failed: openai-ping must output a JSON object.")
            if ping_obj.get("status") != "FAIL":
                raise SystemExit("Smoke test failed: openai-ping must fail when network_access=false.")
            if ping_obj.get("error_code") != "NETWORK_DISABLED":
                raise SystemExit("Smoke test failed: openai-ping must fail with NETWORK_DISABLED when network disabled.")
            if ping_obj.get("redacted") is not True:
                raise SystemExit("Smoke test failed: openai-ping output must include redacted=true.")
        finally:
            policy_security_path.write_text(original_policy_security_ping, encoding="utf-8")

    # Policy editor CLI v0.1: export/validate/diff/apply (safe).
    export_ok = False
    validate_ok = False
    validate_fail = False
    apply_dry_run_fail = False

    proc_export = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "policy", "export", "--name", "policy_security.v1.json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_export.returncode == 0 and '"network_access"' in (proc_export.stdout or ""):
        export_ok = True

    proc_val_ok = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "policy", "validate", "--file", "policies/policy_security.v1.json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_val_ok.returncode == 0 and (proc_val_ok.stdout or "").strip().startswith("OK"):
        validate_ok = True
    else:
        raise SystemExit("Smoke test failed: policy validate should PASS for policy_security.v1.json")

    invalid_policy_path = repo_root / ".cache" / "invalid_policy.json"
    invalid_policy_path.parent.mkdir(parents=True, exist_ok=True)
    base_sec = json.loads((repo_root / "policies" / "policy_security.v1.json").read_text(encoding="utf-8"))
    if not isinstance(base_sec, dict):
        raise SystemExit("Smoke test failed: policy_security.v1.json must be an object.")
    base_sec["__smoke_extra"] = True
    invalid_policy_path.write_text(json.dumps(base_sec, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    proc_val_fail = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "policy", "validate", "--file", str(invalid_policy_path)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_val_fail.returncode != 0:
        validate_fail = True
    else:
        raise SystemExit("Smoke test failed: policy validate should FAIL for invalid_policy.json")

    proc_diff = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.manage",
            "policy",
            "diff",
            "--a",
            "policies/policy_security.v1.json",
            "--b",
            str(invalid_policy_path),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_diff.returncode != 0:
        raise SystemExit("Smoke test failed: policy diff should succeed.")
    try:
        diff_obj = json.loads((proc_diff.stdout or "").strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: policy diff must output JSON.\n" + proc_diff.stdout) from e
    changed_keys = diff_obj.get("changed_keys") if isinstance(diff_obj, dict) else None
    if not (isinstance(changed_keys, list) and "__smoke_extra" in changed_keys):
        raise SystemExit("Smoke test failed: policy diff changed_keys must include __smoke_extra")

    proc_apply = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.ops.manage",
            "policy",
            "apply",
            "--file",
            str(invalid_policy_path),
            "--dry-run",
            "true",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_apply.returncode != 0:
        apply_dry_run_fail = True

    if invalid_policy_path.exists():
        invalid_policy_path.unlink()

    print(
        "CRITICAL_POLICY_EDITOR: "
        + f"export_ok={str(export_ok).lower()} "
        + f"validate_ok={str(validate_ok).lower()} "
        + f"validate_fail={str(validate_fail).lower()} "
        + f"apply_dry_run_fail={str(apply_dry_run_fail).lower()}"
    )

    # Policy schema mapping strictness: strict mapping must fail if schema is missing.
    strict_fail = False
    infer_attempted = False

    unknown_policy_path = repo_root / ".cache" / "policy_unknown.v1.json"
    unknown_policy_path.parent.mkdir(parents=True, exist_ok=True)
    unknown_policy_path.write_text((repo_root / "policies" / "policy_security.v1.json").read_text(encoding="utf-8"), encoding="utf-8")
    try:
        proc_strict = subprocess.run(
            [sys.executable, "-m", "src.ops.manage", "policy", "validate", "--file", str(unknown_policy_path)],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        out_strict = (proc_strict.stdout or "") + "\n" + (proc_strict.stderr or "")
        if proc_strict.returncode != 0 and "SCHEMA_NOT_FOUND" in out_strict:
            strict_fail = True
        else:
            raise SystemExit(
                "Smoke test failed: strict policy schema mapping should fail with SCHEMA_NOT_FOUND.\n"
                + out_strict.strip()
            )

        proc_infer = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "policy",
                "validate",
                "--file",
                str(unknown_policy_path),
                "--infer-schema",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        infer_attempted = True
        out_infer = (proc_infer.stdout or "") + "\n" + (proc_infer.stderr or "")
        if "Traceback" in out_infer:
            raise SystemExit("Smoke test failed: policy validate --infer-schema should not crash.\n" + out_infer.strip())
    finally:
        if unknown_policy_path.exists():
            unknown_policy_path.unlink()

    print(
        "CRITICAL_SCHEMA_MAPPING: "
        + f"strict_fail={str(strict_fail).lower()} "
        + f"infer_attempted={str(infer_attempted).lower()}"
    )

    # Python SDK v0.1: programmatic run (must use local runner, no network required).
    try:
        from src.sdk import OrchestratorClient
    except Exception as e:
        raise SystemExit("Smoke test failed: failed to import SDK OrchestratorClient: " + str(e))

    sdk = OrchestratorClient(workspace=str(repo_root), evidence_dir="evidence")
    sdk_res = sdk.run(
        intent="urn:core:summary:summary_to_file",
        tenant_id="TENANT-LOCAL",
        context=None,
        risk_score=0.1,
        dry_run=True,
        side_effect_policy="none",
    )
    if not isinstance(sdk_res, dict) or sdk_res.get("status") != "OK":
        raise SystemExit("Smoke test failed: SDK run must return status OK.\n" + json.dumps(sdk_res, indent=2, ensure_ascii=False))
    sdk_run_id = sdk_res.get("run_id")
    sdk_evidence_path = sdk_res.get("evidence_path")
    if not isinstance(sdk_run_id, str) or not sdk_run_id:
        raise SystemExit("Smoke test failed: SDK run must return run_id.")
    if not isinstance(sdk_evidence_path, str) or not sdk_evidence_path:
        raise SystemExit("Smoke test failed: SDK run must return evidence_path.")

    evidence_path = Path(sdk_evidence_path)
    evidence_path = (repo_root / evidence_path).resolve() if not evidence_path.is_absolute() else evidence_path.resolve()
    if not evidence_path.exists():
        raise SystemExit("Smoke test failed: SDK evidence_path does not exist: " + str(evidence_path))

    print(f"CRITICAL_SDK_RUN: ok=true run_id={sdk_run_id}")

    sdk_pc = sdk.policy_check(source="fixtures")
    if not isinstance(sdk_pc, dict) or sdk_pc.get("status") != "OK":
        raise SystemExit(
            "Smoke test failed: SDK policy_check must return status OK.\n"
            + json.dumps(sdk_pc, indent=2, ensure_ascii=False)
        )
    report_p = sdk_pc.get("report_path")
    if not isinstance(report_p, str) or not report_p:
        raise SystemExit("Smoke test failed: SDK policy_check must return report_path.")
    report_abs = Path(report_p)
    report_abs = (repo_root / report_abs).resolve() if not report_abs.is_absolute() else report_abs.resolve()
    if not report_abs.exists():
        raise SystemExit("Smoke test failed: SDK policy_check report_path does not exist: " + str(report_abs))

    print(f"CRITICAL_SDK_POLICY_CHECK: ok=true report={report_p}")

    # Roadmap Runner v0.1: compile -> dry-run apply -> apply (demo roadmap is safe: docs + .cache only).
    # Avoid infinite recursion: the demo roadmap gate runs smoke_test.py, which would re-run this section.
    if os.environ.get("ORCH_ROADMAP_RUNNER") != "1":
        demo_roadmap = repo_root / "roadmaps" / "RM-DEMO" / "roadmap.v1.json"
        if not demo_roadmap.exists():
            raise SystemExit("Smoke test failed: missing demo roadmap: roadmaps/RM-DEMO/roadmap.v1.json")

        demo_plan_out = repo_root / ".cache" / "roadmap_plan_demo.json"
        demo_plan_out.parent.mkdir(parents=True, exist_ok=True)

        def plan_hash(path: Path) -> str:
            return sha256(path.read_bytes()).hexdigest()

        proc_plan_1 = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-plan",
                "--roadmap",
                str(demo_roadmap),
                "--out",
                str(demo_plan_out.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_plan_1.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-plan must exit 0.\n"
                + (proc_plan_1.stderr or proc_plan_1.stdout or "")
            )
        if not demo_plan_out.exists():
            raise SystemExit("Smoke test failed: roadmap-plan did not write plan output to .cache/roadmap_plan_demo.json")
        h1 = plan_hash(demo_plan_out)

        proc_plan_2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-plan",
                "--roadmap",
                str(demo_roadmap),
                "--out",
                str(demo_plan_out.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_plan_2.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-plan (2nd run) must exit 0.\n"
                + (proc_plan_2.stderr or proc_plan_2.stdout or "")
            )
        h2 = plan_hash(demo_plan_out)
        if h1 != h2:
            raise SystemExit("Smoke test failed: roadmap plan output must be deterministic (hash mismatch).")

        demo_doc = repo_root / "docs" / "OPERATIONS" / "roadmap-runner-demo.md"
        if demo_doc.exists():
            demo_doc.unlink()

        proc_apply_dry = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                str(demo_roadmap),
                "--dry-run",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_apply_dry.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-apply --dry-run true must exit 0.\n"
                + (proc_apply_dry.stderr or proc_apply_dry.stdout or "")
            )
        if demo_doc.exists():
            raise SystemExit("Smoke test failed: roadmap-apply --dry-run must not create docs/OPERATIONS/roadmap-runner-demo.md")

        try:
            apply_dry_obj = json.loads((proc_apply_dry.stdout or "").strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: roadmap-apply --dry-run must output JSON.") from e
        ev_path_dry = apply_dry_obj.get("evidence_path") if isinstance(apply_dry_obj, dict) else None
        if not isinstance(ev_path_dry, str) or not ev_path_dry:
            raise SystemExit("Smoke test failed: roadmap-apply --dry-run output missing evidence_path.")
        ev_dir_dry = (repo_root / ev_path_dry).resolve()
        if not (ev_dir_dry / "integrity.manifest.v1.json").exists():
            raise SystemExit("Smoke test failed: roadmap evidence must include integrity.manifest.v1.json")

        proc_apply = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                str(demo_roadmap),
                "--dry-run",
                "false",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_apply.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-apply --dry-run false must exit 0.\n"
                + (proc_apply.stderr or proc_apply.stdout or "")
            )
        if not demo_doc.exists():
            raise SystemExit("Smoke test failed: roadmap-apply (apply mode) must create docs/OPERATIONS/roadmap-runner-demo.md")
        # Clean up demo doc to keep local dev less noisy.
        demo_doc.unlink()

        print("CRITICAL_ROADMAP_RUNNER: compile_ok=true dry_run_ok=true apply_ok=true")

        # Roadmap Runner v0.2: SSOT roadmap subset (M2) + dry-run simulate/readonly.
        ssot_roadmap = repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json"
        if not ssot_roadmap.exists():
            raise SystemExit("Smoke test failed: missing SSOT roadmap: roadmaps/SSOT/roadmap.v1.json")

        ssot_plan_out = repo_root / ".cache" / "roadmap_plan_ssot_m2.json"
        ssot_plan_out.parent.mkdir(parents=True, exist_ok=True)

        def git_status_porcelain() -> str:
            proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                text=True,
                capture_output=True,
            )
            if proc.returncode != 0:
                raise SystemExit("Smoke test failed: git status --porcelain failed for readonly roadmap checks.")
            return proc.stdout or ""

        proc_ssot_plan_1 = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-plan",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--out",
                str(ssot_plan_out.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ssot_plan_1.returncode != 0:
            raise SystemExit(
                "Smoke test failed: SSOT roadmap-plan --milestone M2 must exit 0.\n"
                + (proc_ssot_plan_1.stderr or proc_ssot_plan_1.stdout or "")
            )
        if not ssot_plan_out.exists():
            raise SystemExit("Smoke test failed: SSOT roadmap-plan did not write .cache/roadmap_plan_ssot_m2.json")
        ssot_h1 = sha256(ssot_plan_out.read_bytes()).hexdigest()

        proc_ssot_plan_2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-plan",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--out",
                str(ssot_plan_out.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ssot_plan_2.returncode != 0:
            raise SystemExit(
                "Smoke test failed: SSOT roadmap-plan (2nd run) must exit 0.\n"
                + (proc_ssot_plan_2.stderr or proc_ssot_plan_2.stdout or "")
            )
        ssot_h2 = sha256(ssot_plan_out.read_bytes()).hexdigest()
        if ssot_h1 != ssot_h2:
            raise SystemExit("Smoke test failed: SSOT M2 plan output must be deterministic (hash mismatch).")

        baseline_status = git_status_porcelain()
        proc_ssot_sim = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--dry-run",
                "true",
                "--dry-run-mode",
                "simulate",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ssot_sim.returncode != 0:
            raise SystemExit(
                "Smoke test failed: SSOT M2 roadmap-apply dry-run simulate must exit 0.\n"
                + (proc_ssot_sim.stderr or proc_ssot_sim.stdout or "")
            )
        if git_status_porcelain() != baseline_status:
            raise SystemExit("Smoke test failed: SSOT M2 dry-run simulate must not change git status.")

        sim_obj = json.loads((proc_ssot_sim.stdout or "").strip() or "{}")
        sim_ev_path = sim_obj.get("evidence_path") if isinstance(sim_obj, dict) else None
        if not isinstance(sim_ev_path, str) or not sim_ev_path:
            raise SystemExit("Smoke test failed: SSOT M2 dry-run simulate output missing evidence_path.")
        sim_ev_dir = (repo_root / sim_ev_path).resolve()
        if not (sim_ev_dir / "integrity.manifest.v1.json").exists():
            raise SystemExit("Smoke test failed: SSOT M2 roadmap evidence must include integrity.manifest.v1.json (simulate).")

        proc_ssot_ro = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--dry-run",
                "true",
                "--dry-run-mode",
                "readonly",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ssot_ro.returncode != 0:
            raise SystemExit(
                "Smoke test failed: SSOT M2 roadmap-apply dry-run readonly must exit 0.\n"
                + (proc_ssot_ro.stderr or proc_ssot_ro.stdout or "")
            )
        if git_status_porcelain() != baseline_status:
            raise SystemExit("Smoke test failed: SSOT M2 dry-run readonly must not change git status.")

        ro_obj = json.loads((proc_ssot_ro.stdout or "").strip() or "{}")
        ro_ev_path = ro_obj.get("evidence_path") if isinstance(ro_obj, dict) else None
        if not isinstance(ro_ev_path, str) or not ro_ev_path:
            raise SystemExit("Smoke test failed: SSOT M2 dry-run readonly output missing evidence_path.")
        ro_ev_dir = (repo_root / ro_ev_path).resolve()
        if not (ro_ev_dir / "integrity.manifest.v1.json").exists():
            raise SystemExit("Smoke test failed: SSOT M2 roadmap evidence must include integrity.manifest.v1.json (readonly).")

        ro_summary = json.loads((ro_ev_dir / "summary.json").read_text(encoding="utf-8"))
        gate_results = ro_summary.get("gate_results") if isinstance(ro_summary, dict) else None
        smoke_gate_ok = False
        if isinstance(gate_results, list):
            for gr in gate_results:
                if not isinstance(gr, dict):
                    continue
                if gr.get("status") != "OK":
                    continue
                cmd = gr.get("cmd")
                if not isinstance(cmd, str):
                    continue
                if cmd == "python -m src.ops.manage smoke --level fast" or "src.ops.manage smoke" in cmd:
                    smoke_gate_ok = True
                    break
        if not smoke_gate_ok:
            raise SystemExit("Smoke test failed: SSOT M2 readonly must run allowlisted gates (missing OK smoke_test gate result).")

        print("CRITICAL_ROADMAP_RUNNER_V2: plan_ok=true simulate_ok=true readonly_ok=true")

        # Roadmap Runner v0.3: workspace root + change proposals + promotion scan (deterministic, no network).
        roadmap_change_schema = repo_root / "schemas" / "roadmap-change.schema.json"
        promote_manifest_schema = repo_root / "schemas" / "promote.manifest.schema.json"
        if not roadmap_change_schema.exists():
            raise SystemExit("Smoke test failed: missing schemas/roadmap-change.schema.json")
        if not promote_manifest_schema.exists():
            raise SystemExit("Smoke test failed: missing schemas/promote.manifest.schema.json")

        ws_demo = repo_root / ".cache" / "workspace_demo"
        if ws_demo.exists():
            rmtree(ws_demo)
        ws_demo.mkdir(parents=True, exist_ok=True)

        proc_ws_boot = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "workspace-bootstrap",
                "--out",
                str(ws_demo.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ws_boot.returncode != 0:
            raise SystemExit(
                "Smoke test failed: workspace-bootstrap must exit 0.\n" + (proc_ws_boot.stderr or proc_ws_boot.stdout or "")
            )

        def snapshot_files(root: Path) -> dict[str, str]:
            snap: dict[str, str] = {}
            for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
                if not p.is_file():
                    continue
                rel = p.relative_to(root).as_posix()
                snap[rel] = sha256(p.read_bytes()).hexdigest()
            return snap

        ws_snap_before = snapshot_files(ws_demo)

        ssot_plan_ws_out = repo_root / ".cache" / "roadmap_plan_ssot_m2_ws.json"
        proc_plan_ws = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-plan",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--workspace-root",
                str(ws_demo.relative_to(repo_root)),
                "--out",
                str(ssot_plan_ws_out.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_plan_ws.returncode != 0:
            raise SystemExit("Smoke test failed: roadmap-plan with --workspace-root must exit 0.\n" + (proc_plan_ws.stderr or proc_plan_ws.stdout or ""))
        if not ssot_plan_ws_out.exists():
            raise SystemExit("Smoke test failed: roadmap-plan with --workspace-root did not write plan output.")

        baseline_status_ws = git_status_porcelain()
        proc_apply_ws_ro = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--workspace-root",
                str(ws_demo.relative_to(repo_root)),
                "--dry-run",
                "true",
                "--dry-run-mode",
                "readonly",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_apply_ws_ro.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-apply readonly with --workspace-root must exit 0.\n"
                + (proc_apply_ws_ro.stderr or proc_apply_ws_ro.stdout or "")
            )
        if git_status_porcelain() != baseline_status_ws:
            raise SystemExit("Smoke test failed: roadmap-apply readonly with --workspace-root must not change git status.")
        ws_snap_after = snapshot_files(ws_demo)
        if ws_snap_after != ws_snap_before:
            raise SystemExit("Smoke test failed: roadmap-apply readonly with --workspace-root must not write into workspace root.")

        # Change proposal apply (safe): apply to a temporary copy under .cache/ (avoid dirty core repo).
        tmp_roadmap = repo_root / ".cache" / "roadmap_ssot_copy.json"
        tmp_roadmap.write_text(ssot_roadmap.read_text(encoding="utf-8"), encoding="utf-8")

        tmp_change = repo_root / ".cache" / "CHG-20000101-001.json"
        tmp_change_obj = {
            "change_id": "CHG-20000101-001",
            "version": "v1",
            "type": "modify",
            "risk_level": "low",
            "target": {"milestone_id": "M2"},
            "rationale": "Smoke test: append a safe note.",
            "patches": [{"op": "append_milestone_note", "milestone_id": "M2", "note": "SMOKE_CHANGE_NOTE"}],
            "gates": ["python ci/validate_schemas.py", "python -m src.ops.manage smoke --level fast"],
        }
        tmp_change.write_text(json.dumps(tmp_change_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        proc_chg_apply = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-change-apply",
                "--change",
                str(tmp_change.relative_to(repo_root)),
                "--roadmap",
                str(tmp_roadmap.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_chg_apply.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-change-apply must exit 0.\n" + (proc_chg_apply.stderr or proc_chg_apply.stdout or "")
            )

        changed_obj = json.loads(tmp_roadmap.read_text(encoding="utf-8"))
        m2 = None
        for ms in changed_obj.get("milestones", []) if isinstance(changed_obj, dict) else []:
            if isinstance(ms, dict) and ms.get("id") == "M2":
                m2 = ms
                break
        notes = m2.get("notes") if isinstance(m2, dict) else None
        if not (isinstance(notes, list) and "SMOKE_CHANGE_NOTE" in notes):
            raise SystemExit("Smoke test failed: roadmap-change-apply did not modify milestone notes as expected.")

        # Promotion scan: fail-closed when forbidden token exists.
        inc_dir = ws_demo / "incubator"
        inc_dir.mkdir(parents=True, exist_ok=True)
        bad_item = inc_dir / "item.md"
        bad_item.write_text("Beykent", encoding="utf-8")

        proc_promote_scan = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "promote-scan",
                "--root",
                str(inc_dir.relative_to(repo_root)),
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_promote_scan.returncode == 0:
            raise SystemExit("Smoke test failed: promote-scan must fail on forbidden token.")
        try:
            scan_obj = json.loads((proc_promote_scan.stdout or "").strip() or "{}")
        except Exception:
            scan_obj = {}
        if scan_obj.get("error_code") != "SANITIZE_VIOLATION":
            raise SystemExit("Smoke test failed: promote-scan must return SANITIZE_VIOLATION.")

        print("CRITICAL_ROADMAP_RUNNER_V3: workspace_root_ok=true changes_ok=true promote_scan_ok=true")
    else:
        print("NOTE: ORCH_ROADMAP_RUNNER=1; skipping roadmap-runner smoke to avoid recursion.")

    # Roadmap Orchestrator v0.1: state bootstrap + ISO bootstrap (M1) + idempotent file steps.
    # Avoid infinite recursion:
    # - the orchestrator runs smoke_test.py as a post-gate, and that smoke run must not call roadmap-follow again.
    # - roadmap runner gates can also call smoke_test.py with ORCH_ROADMAP_RUNNER=1.
    if os.environ.get("ORCH_ROADMAP_ORCHESTRATOR") != "1" and os.environ.get("ORCH_ROADMAP_RUNNER") != "1":
        from src.roadmap.step_templates import RoadmapStepError, VirtualFS, step_add_ci_gate_script, step_create_file, step_create_json_from_template

        ssot_roadmap = repo_root / "roadmaps" / "SSOT" / "roadmap.v1.json"
        ws_follow = repo_root / ".cache" / "ws_follow_demo"
        rmtree(ws_follow, ignore_errors=True)

        proc_ws = subprocess.run(
            [sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws_follow.relative_to(repo_root))],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ws.returncode != 0:
            raise SystemExit("Smoke test failed: workspace-bootstrap for roadmap-follow failed:\n" + (proc_ws.stderr or proc_ws.stdout or ""))

        # Create M2 workspace artifacts once (out-of-order allowed in this smoke); this enables state bootstrap to detect M2 as completed.
        proc_apply_m2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-apply",
                "--roadmap",
                str(ssot_roadmap),
                "--milestone",
                "M2",
                "--workspace-root",
                str(ws_follow.relative_to(repo_root)),
                "--dry-run",
                "false",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_apply_m2.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-apply M2 (apply mode) must exit 0.\n" + (proc_apply_m2.stderr or proc_apply_m2.stdout or "")
            )

        state_path = ws_follow / ".cache" / "roadmap_state.v1.json"
        if state_path.exists():
            state_path.unlink()

        proc_follow = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-follow",
                "--roadmap",
                str(ssot_roadmap),
                "--workspace-root",
                str(ws_follow.relative_to(repo_root)),
                "--max-steps",
                "1",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        try:
            follow = json.loads((proc_follow.stdout or "").strip() or "{}")
        except Exception:
            follow = {}
        if follow.get("status") != "OK":
            raise SystemExit("Smoke test failed: roadmap-follow must be OK.\n" + (proc_follow.stderr or proc_follow.stdout or ""))
        if not state_path.exists():
            raise SystemExit("Smoke test failed: roadmap-follow must create workspace state file: " + str(state_path))

        st = json.loads(state_path.read_text(encoding="utf-8"))
        completed_ms = st.get("completed_milestones")
        if not isinstance(completed_ms, list):
            raise SystemExit("Smoke test failed: roadmap state completed_milestones must be a list.")
        if "M2" not in completed_ms:
            raise SystemExit("Smoke test failed: state bootstrap must detect M2 as completed when markers exist.")

        # M1 apply must create ISO stub files (or treat them as idempotent no-ops if already present).
        iso_dir = ws_follow / "tenant" / "TENANT-DEFAULT"
        iso_files = [
            iso_dir / "context.v1.md",
            iso_dir / "stakeholders.v1.md",
            iso_dir / "scope.v1.md",
            iso_dir / "criteria.v1.md",
        ]
        if any(not p.exists() for p in iso_files):
            missing = [p.as_posix() for p in iso_files if not p.exists()]
            raise SystemExit("Smoke test failed: M1 ISO bootstrap files missing: " + ", ".join(missing))

        # Idempotent create_file/create_json/add_ci_gate_script behavior (overwrite=false):
        # - same content => OK (noop)
        # - different content => CONTENT_MISMATCH
        virtual_fs = VirtualFS(files={})

        # create_file mismatch (should fail-closed)
        try:
            step_create_file(
                workspace=ws_follow.resolve(),
                virtual_fs=virtual_fs,
                path="tenant/TENANT-DEFAULT/context.v1.md",
                content="DIFFERENT",
                overwrite=False,
                dry_run=False,
            )
            raise SystemExit("Smoke test failed: create_file overwrite=false should fail on content mismatch.")
        except RoadmapStepError as e:
            if e.error_code != "CONTENT_MISMATCH":
                raise SystemExit("Smoke test failed: create_file mismatch must be CONTENT_MISMATCH, got: " + str(e.error_code))

        # create_json_from_template idempotence and mismatch checks
        schema_path = ws_follow / "schemas" / "tenant-decision-bundle.schema.json"
        schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
        res_ok, _, _ = step_create_json_from_template(
            workspace=ws_follow.resolve(),
            virtual_fs=virtual_fs,
            path="schemas/tenant-decision-bundle.schema.json",
            json_obj=schema_obj,
            overwrite=False,
            dry_run=False,
        )
        if res_ok.get("status") != "OK":
            raise SystemExit("Smoke test failed: create_json_from_template idempotent run must return OK.")
        try:
            step_create_json_from_template(
                workspace=ws_follow.resolve(),
                virtual_fs=virtual_fs,
                path="schemas/tenant-decision-bundle.schema.json",
                json_obj={"__smoke_mismatch__": True},
                overwrite=False,
                dry_run=False,
            )
            raise SystemExit("Smoke test failed: create_json_from_template overwrite=false should fail on content mismatch.")
        except RoadmapStepError as e:
            if e.error_code != "CONTENT_MISMATCH":
                raise SystemExit("Smoke test failed: create_json mismatch must be CONTENT_MISMATCH, got: " + str(e.error_code))

        # add_ci_gate_script idempotence and mismatch checks
        script_path = ws_follow / "ci" / "validate_tenant_consistency.py"
        script_text = script_path.read_text(encoding="utf-8")
        res_ci_ok, _, _ = step_add_ci_gate_script(
            workspace=ws_follow.resolve(),
            virtual_fs=virtual_fs,
            path="ci/validate_tenant_consistency.py",
            content=script_text,
            overwrite=False,
            dry_run=False,
        )
        if res_ci_ok.get("status") != "OK":
            raise SystemExit("Smoke test failed: add_ci_gate_script idempotent run must return OK.")
        try:
            step_add_ci_gate_script(
                workspace=ws_follow.resolve(),
                virtual_fs=virtual_fs,
                path="ci/validate_tenant_consistency.py",
                content=script_text + "# mismatch\n",
                overwrite=False,
                dry_run=False,
            )
            raise SystemExit("Smoke test failed: add_ci_gate_script overwrite=false should fail on content mismatch.")
        except RoadmapStepError as e:
            if e.error_code != "CONTENT_MISMATCH":
                raise SystemExit("Smoke test failed: add_ci_gate_script mismatch must be CONTENT_MISMATCH, got: " + str(e.error_code))

        print("CRITICAL_ROADMAP_STATE_BOOTSTRAP: ok=true")

        # Roadmap Orchestrator v0.2: roadmap-finish loop (until DONE/BLOCKED) + actions register.
        ws_finish = repo_root / ".cache" / "ws_finish_demo"
        rmtree(ws_finish, ignore_errors=True)
        proc_ws_finish = subprocess.run(
            [sys.executable, "-m", "src.ops.manage", "workspace-bootstrap", "--out", str(ws_finish.relative_to(repo_root))],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_ws_finish.returncode != 0:
            raise SystemExit(
                "Smoke test failed: workspace-bootstrap for roadmap-finish failed:\n"
                + (proc_ws_finish.stderr or proc_ws_finish.stdout or "")
            )

        # Use a minimal roadmap so finish completes quickly and deterministically.
        finish_roadmap_path = repo_root / ".cache" / "roadmap_finish_demo.v1.json"
        finish_roadmap_obj = {
            "roadmap_id": "RM-FINISH-DEMO",
            "version": "v1",
            "iso_core_required": False,
            "global_gates": [],
            "milestones": [
                {
                    "id": "MF1",
                    "title": "Roadmap Finish Demo",
                    "steps": [{"type": "note", "text": "Finish demo milestone (safe)."}],
                    "gates": [],
                    "dod": [],
                }
            ],
        }
        finish_roadmap_path.write_text(
            json.dumps(finish_roadmap_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        proc_finish = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-finish",
                "--roadmap",
                str(finish_roadmap_path.relative_to(repo_root)),
                "--workspace-root",
                str(ws_finish.relative_to(repo_root)),
                "--max-minutes",
                "1",
                "--sleep-seconds",
                "0",
                "--max-steps-per-iteration",
                "2",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_finish.returncode not in (0, 2):
            raise SystemExit(
                "Smoke test failed: roadmap-finish unexpected exit code.\n"
                + (proc_finish.stderr or proc_finish.stdout or "")
            )
        try:
            finish_obj = json.loads((proc_finish.stdout or "").strip() or "{}")
        except Exception as e:
            raise SystemExit(
                "Smoke test failed: roadmap-finish must output JSON.\n"
                + (proc_finish.stderr or proc_finish.stdout or "")
            ) from e
        if finish_obj.get("status") not in {"DONE", "DONE_WITH_DEBT", "OK", "BLOCKED"}:
            raise SystemExit("Smoke test failed: roadmap-finish invalid status: " + str(finish_obj.get("status")))

        finish_state_path = ws_finish / ".cache" / "roadmap_state.v1.json"
        if not finish_state_path.exists():
            raise SystemExit("Smoke test failed: roadmap-finish must create state file: " + str(finish_state_path))
        try:
            json.loads(finish_state_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("Smoke test failed: roadmap state file must be valid JSON.") from e

        finish_actions_path = ws_finish / ".cache" / "roadmap_actions.v1.json"
        if not finish_actions_path.exists():
            raise SystemExit("Smoke test failed: roadmap-finish must create action register: " + str(finish_actions_path))
        try:
            finish_actions_obj = json.loads(finish_actions_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("Smoke test failed: roadmap actions file must be valid JSON.") from e

        if budget_status == "WARN":
            actions_list = finish_actions_obj.get("actions") if isinstance(finish_actions_obj, dict) else []
            ok = isinstance(actions_list, list) and any(isinstance(a, dict) and (a.get("source") == "SCRIPT_BUDGET" or a.get("kind") == "SCRIPT_BUDGET") and (a.get("target_milestone") == "M0" or a.get("milestone_hint") == "M0") for a in actions_list)
            if not ok:
                raise SystemExit("Smoke test failed: expected SCRIPT_BUDGET action targeting M0 when status=WARN.")
        print(f"CRITICAL_ACTION_REGISTER_BUDGET ok=true status={budget_status}")

        evidence_paths = finish_obj.get("evidence")
        if not (isinstance(evidence_paths, list) and evidence_paths and isinstance(evidence_paths[0], str)):
            raise SystemExit("Smoke test failed: roadmap-finish must return evidence list.")
        finish_ev_dir = repo_root / evidence_paths[0]
        required_finish_files = [finish_ev_dir / p for p in ("input.json", "output.json", "iterations.json", "actions_before.json", "actions_after.json", "script_budget_report.json", "integrity.manifest.v1.json")]
        missing_finish = [str(p) for p in required_finish_files if not p.exists()]
        if missing_finish:
            raise SystemExit("Smoke test failed: roadmap-finish missing evidence files: " + ", ".join(missing_finish))

        previews_dir = finish_ev_dir / "previews"
        if not previews_dir.exists():
            raise SystemExit("Smoke test failed: roadmap-finish must write previews/ in evidence.")
        preview_files = [p for p in previews_dir.iterdir() if p.is_file() and p.suffix == ".json"]
        if not preview_files:
            raise SystemExit("Smoke test failed: roadmap-finish must write at least one preview JSON.")

        print("CRITICAL_ROADMAP_FINISH ok=true")

        # Customer-friendly mode (v0.1): --chat output must be consistent and include a final JSON line.
        proc_chat_status = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-status",
                "--roadmap",
                str(ssot_roadmap.relative_to(repo_root)),
                "--workspace-root",
                str(ws_follow.relative_to(repo_root)),
                "--chat",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_chat_status.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-status --chat true must exit 0.\n"
                + (proc_chat_status.stderr or proc_chat_status.stdout or "")
            )
        chat_text = (proc_chat_status.stdout or "")
        for heading in ("PREVIEW:", "RESULT:", "EVIDENCE:", "ACTIONS:", "NEXT:"):
            if heading not in chat_text:
                raise SystemExit("Smoke test failed: roadmap-status --chat missing heading: " + heading)
        last_line = [ln for ln in chat_text.splitlines() if ln.strip()][-1]
        try:
            json.loads(last_line)
        except Exception as e:
            raise SystemExit("Smoke test failed: roadmap-status --chat last line must be JSON.") from e

        # For smoke determinism, force finish to stop immediately by marking all milestones completed in state.
        milestones = []
        try:
            ssot_obj = json.loads(ssot_roadmap.read_text(encoding="utf-8"))
        except Exception:
            ssot_obj = {}
        for ms in ssot_obj.get("milestones", []) if isinstance(ssot_obj, dict) else []:
            if isinstance(ms, dict) and isinstance(ms.get("id"), str):
                milestones.append(ms["id"])

        state_obj = json.loads(state_path.read_text(encoding="utf-8"))
        state_obj["completed_milestones"] = milestones
        state_obj["bootstrapped"] = True
        state_obj["current_milestone"] = None
        state_path.write_text(json.dumps(state_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        proc_chat_finish = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "roadmap-finish",
                "--roadmap",
                str(ssot_roadmap.relative_to(repo_root)),
                "--workspace-root",
                str(ws_follow.relative_to(repo_root)),
                "--max-minutes",
                "1",
                "--chat",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=sc_env,
        )
        if proc_chat_finish.returncode != 0:
            raise SystemExit(
                "Smoke test failed: roadmap-finish --chat true must exit 0 for DONE.\n"
                + (proc_chat_finish.stderr or proc_chat_finish.stdout or "")
            )
        finish_chat_text = (proc_chat_finish.stdout or "")
        for heading in ("PREVIEW:", "RESULT:", "EVIDENCE:", "ACTIONS:", "NEXT:"):
            if heading not in finish_chat_text:
                raise SystemExit("Smoke test failed: roadmap-finish --chat missing heading: " + heading)
        finish_last_line = [ln for ln in finish_chat_text.splitlines() if ln.strip()][-1]
        try:
            json.loads(finish_last_line)
        except Exception as e:
            raise SystemExit("Smoke test failed: roadmap-finish --chat last line must be JSON.") from e

        print("CRITICAL_CUSTOMER_MODE ok=true")
    else:
        print("NOTE: ORCH_ROADMAP_ORCHESTRATOR=1 or ORCH_ROADMAP_RUNNER=1; skipping roadmap-autopilot smoke to avoid recursion.")

    # Ops management CLI (no UI): must run and be deterministic.
    proc_runs = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "runs", "--limit", "5"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_runs.returncode != 0:
        raise SystemExit("Smoke test failed: ops manage runs failed:\n" + (proc_runs.stderr or proc_runs.stdout or ""))

    proc_dlq = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "dlq", "--limit", "5"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_dlq.returncode != 0:
        raise SystemExit("Smoke test failed: ops manage dlq failed:\n" + (proc_dlq.stderr or proc_dlq.stdout or ""))

    proc_susp = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "suspends", "--limit", "5"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_susp.returncode != 0:
        raise SystemExit("Smoke test failed: ops manage suspends failed:\n" + (proc_susp.stderr or proc_susp.stdout or ""))

    proc_runs_json = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "runs", "--limit", "50", "--json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_runs_json.returncode != 0:
        raise SystemExit("Smoke test failed: ops manage runs --json failed:\n" + (proc_runs_json.stderr or proc_runs_json.stdout or ""))
    try:
        runs_list = json.loads((proc_runs_json.stdout or "").strip() or "[]")
    except Exception as e:
        raise SystemExit("Smoke test failed: ops manage runs --json did not output valid JSON: " + str(e))
    if not isinstance(runs_list, list):
        raise SystemExit("Smoke test failed: ops manage runs --json must output a JSON list.")
    required_run_fields = {
        "integrity",
        "provenance_status",
        "provenance_created_at",
        "replay_of",
        "replay_warnings",
    }
    if any(
        not isinstance(item, dict) or any(k not in item for k in required_run_fields)
        for item in runs_list
    ):
        raise SystemExit("Smoke test failed: ops manage runs --json missing integrity/provenance fields.")
    if any(
        isinstance(item, dict) and item.get("provenance_status") not in {"OK", "NO_PROV"}
        for item in runs_list
    ):
        raise SystemExit("Smoke test failed: ops manage runs --json provenance_status must be OK or NO_PROV.")
    if any(
        isinstance(item, dict)
        and item.get("replay_of") is not None
        and not isinstance(item.get("replay_of"), str)
        for item in runs_list
    ):
        raise SystemExit("Smoke test failed: ops manage runs --json replay_of must be string or null.")
    if any(
        isinstance(item, dict) and not isinstance(item.get("replay_warnings"), list)
        for item in runs_list
    ):
        raise SystemExit("Smoke test failed: ops manage runs --json replay_warnings must be a list.")

    proc_susp_json = subprocess.run(
        [sys.executable, "-m", "src.ops.manage", "suspends", "--limit", "50", "--json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        env=sc_env,
    )
    if proc_susp_json.returncode != 0:
        raise SystemExit("Smoke test failed: ops manage suspends --json failed:\n" + (proc_susp_json.stderr or proc_susp_json.stdout or ""))
    try:
        susp_list = json.loads((proc_susp_json.stdout or "").strip() or "[]")
    except Exception as e:
        raise SystemExit("Smoke test failed: ops manage suspends --json did not output valid JSON: " + str(e))
    if not isinstance(susp_list, list):
        raise SystemExit("Smoke test failed: ops manage suspends --json must output a JSON list.")

    dlq_dir = repo_root / "dlq"
    dlq_count = len(list(dlq_dir.glob("*.json"))) if dlq_dir.exists() else 0

    print("CRITICAL_OPS_RUNS_COUNT " + str(len(runs_list)))
    print("CRITICAL_OPS_DLQ_COUNT " + str(dlq_count))
    print("CRITICAL_OPS_SUSPENDS_COUNT " + str(len(susp_list)))

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
