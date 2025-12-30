import json
import subprocess
import sys
from pathlib import Path
from shutil import rmtree


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

    # Repo hygiene guard: ensure critical JSON config files are NOT ignored.
    # (In CI, checkout is a git work tree; locally we skip if not in git.)
    if is_git_work_tree(repo_root):
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

    idempotency_store_path = repo_root / ".cache" / "idempotency_store.v1.json"
    if idempotency_store_path.exists():
        idempotency_store_path.unlink()

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
    required_files = [
        evidence_dir / "request.json",
        evidence_dir / "summary.json",
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
        "workflow_fingerprint",
        "started_at",
        "finished_at",
        "duration_ms",
        "idempotency_key_hash",
    ]
    missing_keys = [k for k in required_summary_keys if k not in summary_file]
    if missing_keys:
        raise SystemExit("Smoke test failed: missing summary keys:\n" + "\n".join(missing_keys))

    if summary_file.get("run_id") != run_id:
        raise SystemExit("Smoke test failed: summary.json run_id mismatch.")

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

    out_dir_bad = smoke_root / "invalid"

    dlq_dir = repo_root / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)
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

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
