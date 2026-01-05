from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from datetime import datetime, timezone
from pathlib import Path

from src.ops.commands.common import git_ref_exists, is_git_work_tree, repo_root, run_step, warn, write_json
from src.ops.reaper import compute_reaper_report, parse_bool as parse_reaper_bool, parse_iso8601 as parse_reaper_iso, write_report as write_reaper_report


def cmd_reaper(args: argparse.Namespace) -> int:
    root = repo_root()
    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError as e:
        warn("ERROR: " + str(e))
        return 2

    if args.now:
        try:
            now = parse_reaper_iso(str(args.now))
        except Exception as e:
            warn("ERROR: Invalid --now: " + str(e))
            return 2
    else:
        now = datetime.now(timezone.utc)

    report = compute_reaper_report(root=root, dry_run=dry_run, now=now)
    if args.out:
        out_path = Path(str(args.out))
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
        write_reaper_report(out_path, report)

    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    dlq = report.get("dlq") if isinstance(report.get("dlq"), dict) else {}
    cache = report.get("cache") if isinstance(report.get("cache"), dict) else {}

    print(
        "reaper "
        + f"dry_run={bool(report.get('dry_run'))} "
        + f"evidence_candidates={int(evidence.get('candidates', 0))} "
        + f"dlq_candidates={int(dlq.get('candidates', 0))} "
        + f"cache_candidates={int(cache.get('candidates', 0))} "
        + f"deleted_total={int(evidence.get('deleted', 0)) + int(dlq.get('deleted', 0)) + int(cache.get('deleted', 0))}"
    )
    return 0


def cmd_evidence_export(args: argparse.Namespace) -> int:
    root = repo_root()

    run_arg = str(args.run).strip() if args.run else ""
    if not run_arg:
        print(json.dumps({"status": "FAIL", "reason": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    run_path = Path(run_arg)
    run_dir = (root / run_path).resolve() if not run_path.is_absolute() else run_path.resolve()

    if not run_dir.exists():
        # Treat as run_id and locate under evidence/.
        evidence_dir = root / "evidence"
        direct = evidence_dir / run_arg
        if direct.exists() and direct.is_dir():
            run_dir = direct
        else:
            matches = sorted(
                [
                    p
                    for p in evidence_dir.rglob(run_arg)
                    if p.is_dir() and p.name == run_arg and (p / "summary.json").exists()
                ],
                key=lambda p: p.as_posix(),
            )
            if not matches:
                print(
                    json.dumps(
                        {"status": "FAIL", "reason": "RUN_NOT_FOUND", "run_id": run_arg},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                return 2
            run_dir = matches[0]

    out_path = Path(str(args.out))
    out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()

    try:
        force = parse_reaper_bool(str(args.force))
    except ValueError:
        print(json.dumps({"status": "FAIL", "reason": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    from src.ops.evidence_export import export_evidence_zip

    code, payload = export_evidence_zip(run_dir=run_dir, out_zip=out_path, force=force)
    try:
        payload["out"] = out_path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        pass
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if int(code) == 0 else 2


def _policy_check_generate_report(*, root: Path, outdir: Path) -> Path:
    report_path = outdir / "POLICY_REPORT.md"
    try:
        from src.ops.policy_report import generate_policy_report_markdown

        md = generate_policy_report_markdown(in_dir=outdir, root=root)
        report_path.write_text(md, encoding="utf-8")
    except Exception:
        report_path.write_text("# Policy Check Report\n\n(Report generation failed.)\n", encoding="utf-8")
    return report_path


def _policy_check_read_sim_counts(sim_out: Path) -> tuple[int, int, int, int]:
    try:
        sim = json.loads(sim_out.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError("Failed to parse sim_report.json") from e

    counts = sim.get("counts") if isinstance(sim, dict) else None
    if not isinstance(counts, dict):
        raise ValueError("sim_report.json missing counts")

    allow = int(counts.get("allow", 0))
    suspend = int(counts.get("suspend", 0))
    block = int(counts.get("block_unknown_intent", 0))
    invalid = int(counts.get("invalid_envelope", 0))
    return (allow, suspend, block, invalid)


def _policy_check_read_diff_nonzero(diff_out: Path) -> int:
    if not diff_out.exists():
        return 0
    try:
        diff = json.loads(diff_out.read_text(encoding="utf-8"))
    except Exception:
        return 0

    if isinstance(diff, dict) and diff.get("status") == "SKIPPED":
        return 0

    diff_counts = diff.get("diff_counts") if isinstance(diff, dict) else None
    if not isinstance(diff_counts, dict):
        return 0
    return sum(int(v) for v in diff_counts.values() if isinstance(v, int) and v > 0)


def cmd_policy_check(args: argparse.Namespace) -> int:
    root = repo_root()
    source = str(args.source)
    fixtures = str(args.fixtures)
    evidence = str(args.evidence)
    baseline = str(args.baseline)

    outdir = Path(str(args.outdir))
    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    sim_out = outdir / "sim_report.json"
    diff_out = outdir / "policy_diff_report.json"

    rc, _, _ = run_step(
        root,
        [sys.executable, str(root / "ci" / "validate_schemas.py")],
        stage="SCHEMA_VALIDATE",
    )
    if rc != 0:
        return 2

    rc, _, _ = run_step(
        root,
        [
            sys.executable,
            str(root / "ci" / "policy_dry_run.py"),
            "--source",
            source,
            "--fixtures",
            fixtures,
            "--evidence",
            evidence,
            "--out",
            str(sim_out),
        ],
        stage="POLICY_DRY_RUN",
    )
    if rc != 0:
        return 2

    # Optional policy diff sim (baseline vs candidate).
    if is_git_work_tree(root) and git_ref_exists(root, baseline):
        rc, _, _ = run_step(
            root,
            [
                sys.executable,
                str(root / "ci" / "policy_diff_sim.py"),
                "--source",
                source,
                "--fixtures",
                fixtures,
                "--evidence",
                evidence,
                "--baseline",
                baseline,
                "--out",
                str(diff_out),
            ],
            stage="POLICY_DIFF_SIM",
        )
        if rc != 0:
            return 2
    else:
        write_json(diff_out, {"status": "SKIPPED", "reason": "NO_GIT_OR_BASELINE"})

    # Supply-chain: SBOM + sign + verify (no secrets printed).
    # This can be skipped for orchestrated dry-run tasks to avoid creating/updating
    # artifacts outside .cache (sbom/signature default to supply_chain/).
    skip_supply_chain_raw = (os.environ.get("POLICY_CHECK_SKIP_SUPPLY_CHAIN") or "").strip().lower()
    skip_supply_chain = skip_supply_chain_raw in {"1", "true", "yes"}
    supply_chain_status = "OK"
    if skip_supply_chain:
        supply_chain_status = "SKIPPED"
    else:
        rc, _, _ = run_step(
            root,
            [sys.executable, str(root / "supply_chain" / "sbom.py")],
            stage="SUPPLY_CHAIN_SBOM",
        )
        if rc != 0:
            return 2

        rc, _, _ = run_step(
            root,
            [sys.executable, str(root / "supply_chain" / "sign.py")],
            stage="SUPPLY_CHAIN_SIGN",
        )
        if rc != 0:
            return 2

        rc, _, _ = run_step(
            root,
            [sys.executable, str(root / "supply_chain" / "verify.py")],
            stage="SUPPLY_CHAIN_VERIFY",
        )
        if rc != 0:
            return 2

    report_path = _policy_check_generate_report(root=root, outdir=outdir)

    try:
        report_display = report_path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        report_display = str(report_path)
    print(f"POLICY_REPORT_WRITTEN path={report_display}")

    try:
        allow, suspend, block, invalid = _policy_check_read_sim_counts(sim_out)
    except ValueError as e:
        print("POLICY_CHECK_FAIL stage=READ_SIM_REPORT message=" + str(e))
        return 2

    diff_nonzero = _policy_check_read_diff_nonzero(diff_out)

    outdir_display = None
    try:
        outdir_display = outdir.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        outdir_display = str(outdir)

    print(
        "POLICY_CHECK_OK "
        + f"source={source} "
        + f"dry_run_counts=allow={allow},suspend={suspend},block={block},invalid={invalid} "
        + f"diff_nonzero={diff_nonzero} "
        + f"supply_chain={supply_chain_status} "
        + f"outdir={outdir_display}"
    )
    return 0


def cmd_script_budget(args: argparse.Namespace) -> int:
    root = repo_root()

    out_arg = str(args.out).strip() if getattr(args, "out", None) else ""
    if out_arg:
        out_path = Path(out_arg)
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
    else:
        out_path = (root / ".cache" / "script_budget" / "report.json").resolve()

    rc, _, _ = run_step(
        root,
        [sys.executable, str(root / "ci" / "check_script_budget.py"), "--out", str(out_path)],
        stage="SCRIPT_BUDGET",
    )

    status = "FAIL"
    hard_exceeded = 0
    soft_exceeded = 0
    try:
        report = json.loads(out_path.read_text(encoding="utf-8"))
        if isinstance(report, dict):
            status = str(report.get("status") or "FAIL")
            exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []
            exceeded_soft = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
            function_hard = report.get("function_hard") if isinstance(report.get("function_hard"), list) else []
            function_soft = report.get("function_soft") if isinstance(report.get("function_soft"), list) else []
            hard_exceeded = len(exceeded_hard) + len(function_hard)
            soft_exceeded = len(exceeded_soft) + len(function_soft)
    except Exception:
        pass

    try:
        out_display = out_path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        out_display = str(out_path)
    print(f"SCRIPT_BUDGET status={status} hard_exceeded={hard_exceeded} soft_exceeded={soft_exceeded} report={out_display}")

    return 0 if int(rc) == 0 and status in {"OK", "WARN"} else 2


def cmd_smoke(args: argparse.Namespace) -> int:
    root = repo_root()
    level = str(args.level).strip().lower()
    if level not in {"fast", "full"}:
        warn("FAIL error=INVALID_LEVEL")
        return 2

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = level
    proc = subprocess.run([sys.executable, "smoke_test.py"], cwd=root, text=True, env=env)
    status = "OK" if proc.returncode == 0 else "FAIL"
    print(json.dumps({"status": status, "level": level}, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 2


def cmd_system_status(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    from src.ops.system_status_report import run_system_status

    res = run_system_status(workspace_root=ws, core_root=root, dry_run=bool(dry_run))
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE", "WARN"} else 2


def cmd_promotion_bundle(args: argparse.Namespace) -> int:
    root = repo_root()
    workspace_arg = str(args.workspace_root).strip()
    if not workspace_arg:
        warn("FAIL error=WORKSPACE_ROOT_REQUIRED")
        return 2

    ws = Path(workspace_arg)
    ws = (root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    if not ws.exists() or not ws.is_dir():
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    mode = str(args.mode).strip() if getattr(args, "mode", None) else ""

    from src.ops.promotion_bundle import run_promotion_bundle

    res = run_promotion_bundle(
        workspace_root=ws,
        core_root=root,
        mode=mode if mode else None,
        dry_run=bool(dry_run),
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_WRITE", "WARN"} else 2


def cmd_repo_hygiene(args: argparse.Namespace) -> int:
    root = repo_root()
    mode = str(args.mode).strip().lower()
    if mode not in {"report", "suggest"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    layout_arg = str(args.layout).strip() if args.layout else "docs/OPERATIONS/repo-layout.v1.json"
    out_arg = str(args.out).strip() if args.out else ".cache/repo_hygiene/report.json"

    layout_path = Path(layout_arg)
    if not layout_path.is_absolute():
        layout_path = (root / layout_path).resolve()
    out_path = Path(out_arg)
    if not out_path.is_absolute():
        out_path = (root / out_path).resolve()

    from src.ops.repo_hygiene import run_repo_hygiene

    res = run_repo_hygiene(
        repo_root=root,
        layout_path=layout_path,
        out_path=out_path,
        mode=mode,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2


def cmd_doc_graph(args: argparse.Namespace) -> int:
    root = repo_root()
    ws_arg = str(args.workspace_root).strip()
    if not ws_arg:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    ws_path = Path(ws_arg)
    if not ws_path.is_absolute():
        ws_path = (root / ws_path).resolve()

    mode = str(args.mode).strip().lower()
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    out_arg = str(args.out).strip() if args.out else ".cache/reports/doc_graph_report.v1.json"
    out_path = Path(out_arg)
    if not out_path.is_absolute():
        out_path = (ws_path / out_path).resolve()

    from src.ops.doc_graph import run_doc_graph

    res = run_doc_graph(
        repo_root=root,
        workspace_root=ws_path,
        out_json=out_path,
        mode=mode,
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    if mode == "strict" and res.get("status") == "FAIL":
        return 2
    return 0


def _ensure_workspace_root(root: Path, ws_path: Path) -> tuple[bool, str | None]:
    if ws_path.exists() and ws_path.is_dir():
        return (True, None)
    try:
        from src.ops.roadmap_cli import cmd_workspace_bootstrap
    except Exception:
        return (False, "BOOTSTRAP_UNAVAILABLE")

    buf = StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        rc = cmd_workspace_bootstrap(argparse.Namespace(out=str(ws_path)))
    if rc != 0:
        return (False, "BOOTSTRAP_FAILED")
    return (True, None)


def cmd_doc_nav_check(args: argparse.Namespace) -> int:
    root = repo_root()
    ws_arg = str(args.workspace_root).strip()
    if not ws_arg:
        warn("FAIL error=WORKSPACE_ROOT_INVALID")
        return 2

    ws_path = Path(ws_arg)
    if not ws_path.is_absolute():
        ws_path = (root / ws_path).resolve()

    ok, err = _ensure_workspace_root(root, ws_path)
    if not ok:
        print(json.dumps({"status": "FAIL", "error_code": err}, ensure_ascii=False, sort_keys=True))
        return 2

    detail = parse_reaper_bool(str(args.detail))
    strict = parse_reaper_bool(str(args.strict))
    chat = parse_reaper_bool(str(args.chat))
    mode = "strict" if strict else "report"

    from src.ops.doc_graph import run_doc_graph

    doc_out_name = "doc_graph_report.strict.v1.json" if strict else "doc_graph_report.v1.json"
    doc_out = ws_path / ".cache" / "reports" / doc_out_name
    doc_report = run_doc_graph(repo_root=root, workspace_root=ws_path, out_json=doc_out, mode=mode)

    sys_out_path = ws_path / ".cache" / "reports" / "system_status.v1.json"
    if not strict:
        from src.ops.system_status_report import run_system_status

        sys_result = run_system_status(workspace_root=ws_path, core_root=root, dry_run=False)
        sys_out = sys_result.get("out_json") if isinstance(sys_result, dict) else None
        sys_out_path = (
            Path(str(sys_out))
            if isinstance(sys_out, str)
            else (ws_path / ".cache" / "reports" / "system_status.v1.json")
        )
    sys_obj: dict[str, Any] = {}
    try:
        sys_obj = json.loads(sys_out_path.read_text(encoding="utf-8"))
    except Exception:
        sys_obj = {}

    counts = doc_report.get("counts") if isinstance(doc_report, dict) else {}
    broken_refs = int(counts.get("broken_refs", 0))
    ambiguity = int(counts.get("ambiguity_count", counts.get("ambiguity", 0)))
    orphan_critical = int(counts.get("orphan_critical", 0))
    critical_nav_gaps = int(counts.get("critical_nav_gaps", 0))
    workspace_bound_refs = int(counts.get("workspace_bound_refs_count", 0))
    external_pointer_refs = int(counts.get("external_pointer_refs_count", 0))
    placeholder_refs = int(counts.get("placeholder_refs_count", 0))
    doc_status = doc_report.get("status") if isinstance(doc_report, dict) else "WARN"
    if doc_status not in {"OK", "WARN", "FAIL"}:
        doc_status = "WARN"

    cockpit_sections = sys_obj.get("sections") if isinstance(sys_obj, dict) else {}
    readiness = ""
    if isinstance(cockpit_sections, dict):
        readiness = str(cockpit_sections.get("readiness", {}).get("status", ""))
    core_lock_obj = cockpit_sections.get("core_lock") if isinstance(cockpit_sections, dict) else {}
    core_lock = "ENABLED" if isinstance(core_lock_obj, dict) and core_lock_obj.get("enabled") else "DISABLED"
    project_boundary_obj = cockpit_sections.get("project_boundary") if isinstance(cockpit_sections, dict) else {}
    project_boundary = str(project_boundary_obj.get("status", "WARN")) if isinstance(project_boundary_obj, dict) else "WARN"

    status = "OK"
    if doc_status == "FAIL" or critical_nav_gaps > 0:
        status = "FAIL"
    elif doc_status == "WARN" or str(sys_obj.get("overall_status", "")) in {"WARN", "NOT_READY"}:
        status = "WARN"

    top_broken = doc_report.get("broken_refs") if detail and isinstance(doc_report, dict) else []
    top_orphans = doc_report.get("orphan_critical") if detail and isinstance(doc_report, dict) else []
    top_placeholders = doc_report.get("top_placeholders") if detail and isinstance(doc_report, dict) else []
    if not isinstance(top_broken, list):
        top_broken = []
    if not isinstance(top_orphans, list):
        top_orphans = []
    if not isinstance(top_placeholders, list):
        top_placeholders = []

    notes = ["PROGRAM_LED=true", f"detail={str(detail).lower()}", f"strict={str(strict).lower()}"]
    if strict:
        notes.append(f"strict_report_path={str(Path('.cache') / 'reports' / doc_out_name)}")

    payload = {
        "status": status,
        "workspace_root": str(ws_path),
        "doc_graph": {
            "status": doc_status,
            "broken_refs": broken_refs,
            "ambiguity": ambiguity,
            "orphan_critical": orphan_critical,
            "critical_nav_gaps": critical_nav_gaps,
            "workspace_bound_refs": workspace_bound_refs,
            "external_pointer_refs": external_pointer_refs,
            "placeholder_refs_count": placeholder_refs,
            "top_broken": top_broken if detail else [],
            "top_orphans": top_orphans if detail else [],
            "top_placeholders": top_placeholders if detail else [],
        },
        "cockpit": {
            "overall_status": str(sys_obj.get("overall_status", "")),
            "readiness": readiness,
            "core_lock": core_lock,
            "project_boundary": project_boundary,
        },
        "evidence_paths": [
            str(Path(".cache") / "reports" / doc_out_name),
            str(Path(".cache") / "reports" / "system_status.v1.json"),
        ],
        "notes": notes,
    }

    if chat:
        print("PREVIEW:")
        if strict:
            print("PROGRAM-LED: doc-graph (strict) çalıştırıldı; cockpit refresh yapılmadı; kullanıcı komut yazmadı.")
        else:
            print("PROGRAM-LED: doc-graph + system-status çalıştırıldı; kullanıcı komut yazmadı.")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(
            "status="
            + str(status)
            + f" broken_refs={broken_refs} ambiguity={ambiguity} orphan_critical={orphan_critical} critical_nav_gaps={critical_nav_gaps}"
        )
        print("EVIDENCE:")
        for p in payload.get("evidence_paths", []):
            print(str(p))
        print("ACTIONS:")
        actions: list[str] = []
        if critical_nav_gaps > 0:
            actions.append(f"critical_nav_gaps={critical_nav_gaps}")
        if broken_refs > 0:
            actions.append(f"broken_refs={broken_refs}")
        if ambiguity > 0:
            actions.append(f"ambiguity={ambiguity}")
        if orphan_critical > 0:
            actions.append(f"orphan_critical={orphan_critical}")
        for item in actions[:5]:
            print(item)
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if status == "FAIL":
        return 2
    return 0


def register_maintenance_subcommands(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap_reaper = parent.add_parser("reaper", help="Run retention reaper (dry-run supported).")
    ap_reaper.add_argument("--dry-run", default="true", help="true|false")
    ap_reaper.add_argument("--now", help="ISO8601 timestamp (optional).")
    ap_reaper.add_argument("--out", help="Optional report JSON output path.")
    ap_reaper.set_defaults(func=cmd_reaper)

    ap_export = parent.add_parser("evidence-export", help="Export one evidence run as a zip (integrity-checked).")
    ap_export.add_argument("--run", required=True, help="Run id or path to evidence/<run_id> directory.")
    ap_export.add_argument("--out", required=True, help="Output zip path.")
    ap_export.add_argument("--force", default="false", help="true|false (default: false).")
    ap_export.set_defaults(func=cmd_evidence_export)

    ap_pc = parent.add_parser("policy-check", help="Validate + simulate policy impact (safe local workflow).")
    ap_pc.add_argument("--source", choices=["fixtures", "evidence", "both"], default="fixtures")
    ap_pc.add_argument("--baseline", default="HEAD~1", help="Git ref for baseline (default: HEAD~1).")
    ap_pc.add_argument("--fixtures", default="fixtures/envelopes")
    ap_pc.add_argument("--evidence", default="evidence")
    ap_pc.add_argument("--outdir", default=".cache/policy_check")
    ap_pc.set_defaults(func=cmd_policy_check)

    ap_sb = parent.add_parser("script-budget", help="Run Script Budget guardrails (soft=warn, hard=fail).")
    ap_sb.add_argument("--out", default=".cache/script_budget/report.json", help="Report JSON output path.")
    ap_sb.set_defaults(func=cmd_script_budget)

    ap_smoke = parent.add_parser("smoke", help="Run smoke_test.py with SMOKE_LEVEL (fast|full).")
    ap_smoke.add_argument("--level", default="fast", help="fast|full (default: fast).")
    ap_smoke.set_defaults(func=cmd_smoke)

    ap_sys = parent.add_parser("system-status", help="Generate unified system status report (JSON + MD).")
    ap_sys.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_sys.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_sys.set_defaults(func=cmd_system_status)

    ap_prom = parent.add_parser("promotion-bundle", help="Create promotion bundle from incubator (draft-only).")
    ap_prom.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_prom.add_argument("--mode", default="", help="customer_clean|internal_dev (default: policy).")
    ap_prom.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_prom.set_defaults(func=cmd_promotion_bundle)

    ap_hygiene = parent.add_parser("repo-hygiene", help="Repo hygiene report (warn-only, no auto-fix).")
    ap_hygiene.add_argument("--mode", default="report", help="report|suggest (default: report).")
    ap_hygiene.add_argument("--layout", default="docs/OPERATIONS/repo-layout.v1.json")
    ap_hygiene.add_argument("--out", default=".cache/repo_hygiene/report.json")
    ap_hygiene.set_defaults(func=cmd_repo_hygiene)

    ap_doc = parent.add_parser("doc-graph", help="Doc graph scan (workspace report, warn-only by default).")
    ap_doc.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_doc.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_doc.add_argument("--out", default=".cache/reports/doc_graph_report.v1.json")
    ap_doc.set_defaults(func=cmd_doc_graph)

    ap_nav = parent.add_parser("doc-nav-check", help="Program-led doc nav check (doc-graph + system-status).")
    ap_nav.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_nav.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_nav.add_argument("--strict", default="false", help="true|false (default: false).")
    ap_nav.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_nav.set_defaults(func=cmd_doc_nav_check)
