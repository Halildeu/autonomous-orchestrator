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
from typing import Any

from src.ops.commands.common import git_ref_exists, is_git_work_tree, repo_root, run_step, warn, write_json
from src.ops.commands.maintenance_doc_cmds import cmd_doc_graph, cmd_doc_nav_check
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


def cmd_integrity_verify(args: argparse.Namespace) -> int:
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

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    from src.ops.integrity_verify import run_integrity_verify

    res = run_integrity_verify(workspace_root=ws, mode=mode)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    verify = res.get("verify_on_read_result") if isinstance(res, dict) else None
    if mode == "strict" and verify == "FAIL":
        return 2
    return 0 if res.get("status") in {"OK", "SKIPPED"} else 2


def cmd_work_intake_build(args: argparse.Namespace) -> int:
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

    from src.ops.work_intake_from_sources import run_work_intake_build

    res = run_work_intake_build(workspace_root=ws)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    status = res.get("status") if isinstance(res, dict) else None
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_work_intake_check(args: argparse.Namespace) -> int:
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

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))
    detail = parse_reaper_bool(str(args.detail))

    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.system_status_report import run_system_status
    from src.ops.roadmap_cli import cmd_portfolio_status

    build_res = run_work_intake_build(workspace_root=ws)
    work_intake_path = build_res.get("work_intake_path") if isinstance(build_res, dict) else None

    intake_obj: dict[str, Any] = {}
    if isinstance(work_intake_path, str) and work_intake_path:
        intake_path_abs = (ws / work_intake_path).resolve()
        try:
            intake_obj = json.loads(intake_path_abs.read_text(encoding="utf-8"))
        except Exception:
            intake_obj = {}

    plan_policy = intake_obj.get("plan_policy") if isinstance(intake_obj.get("plan_policy"), str) else "optional"
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    summary = intake_obj.get("summary") if isinstance(intake_obj.get("summary"), dict) else {}
    counts_by_bucket = summary.get("counts_by_bucket") if isinstance(summary.get("counts_by_bucket"), dict) else {}
    top_next_actions = summary.get("top_next_actions") if isinstance(summary.get("top_next_actions"), list) else []
    next_intake_focus = summary.get("next_intake_focus") if isinstance(summary.get("next_intake_focus"), str) else "NONE"

    sys_result = run_system_status(workspace_root=ws, core_root=root, dry_run=False)
    sys_out = sys_result.get("out_json") if isinstance(sys_result, dict) else None
    sys_rel = None
    if isinstance(sys_out, str):
        sys_rel = Path(sys_out).resolve()
        try:
            sys_rel = sys_rel.relative_to(ws)
        except Exception:
            sys_rel = None

    portfolio_buf = StringIO()
    with redirect_stdout(portfolio_buf), redirect_stderr(portfolio_buf):
        cmd_portfolio_status(argparse.Namespace(workspace_root=str(ws), mode="json"))
    portfolio_report = ws / ".cache" / "reports" / "portfolio_status.v1.json"
    portfolio_rel = ".cache/reports/portfolio_status.v1.json" if portfolio_report.exists() else ""

    status = build_res.get("status") if isinstance(build_res, dict) else "WARN"
    error_code = None
    plan_dir = ws / ".cache" / "reports" / "chg"
    plan_missing = False
    if plan_policy == "required" and items:
        if not plan_dir.exists():
            plan_missing = True
        else:
            plans = list(plan_dir.glob("CHG-INTAKE-*.plan.json"))
            plan_missing = not bool(plans)
        if plan_missing:
            status = "IDLE"
            error_code = "NO_PLAN_FOUND"

    payload = {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(ws),
        "work_intake_path": work_intake_path,
        "items_count": len(items),
        "counts_by_bucket": counts_by_bucket,
        "top_next_actions": top_next_actions if detail else top_next_actions[:5],
        "next_intake_focus": next_intake_focus,
        "system_status_path": str(sys_rel) if isinstance(sys_rel, Path) else None,
        "portfolio_status_path": portfolio_rel,
        "notes": [f"mode={mode}", "PROGRAM_LED=true"],
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: work-intake-build + system-status + portfolio-status; user_command=false")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(f"status={status} items={len(items)} next_intake_focus={next_intake_focus}")
        if error_code:
            print(f"error_code={error_code}")
        print("EVIDENCE:")
        for p in [work_intake_path, payload.get("system_status_path"), portfolio_rel]:
            if p:
                print(str(p))
        print("ACTIONS:")
        if plan_missing:
            print("auto-plan_uret")
            print("yeni_plan_ekle")
            print("durumu_goster")
        else:
            if top_next_actions:
                for item in top_next_actions[:5]:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"{item.get('intake_id')} bucket={item.get('bucket')} "
                        f"priority={item.get('priority')}"
                    )
            else:
                print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_work_intake_exec_ticket(args: argparse.Namespace) -> int:
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
        limit = max(0, int(args.limit))
    except Exception:
        warn("FAIL error=INVALID_LIMIT")
        return 2
    chat = parse_reaper_bool(str(args.chat))

    from src.ops.work_intake_exec_ticket import run_work_intake_exec_ticket

    res = run_work_intake_exec_ticket(workspace_root=ws, limit=limit)
    status = res.get("status") if isinstance(res, dict) else "WARN"
    report_rel = res.get("work_intake_exec_path") if isinstance(res, dict) else None
    report_path = (ws / report_rel).resolve() if isinstance(report_rel, str) else None
    entries = []
    if report_path and report_path.exists():
        try:
            report_obj = json.loads(report_path.read_text(encoding="utf-8"))
            entries = report_obj.get("entries") if isinstance(report_obj.get("entries"), list) else []
        except Exception:
            entries = []

    payload = {
        "status": status,
        "workspace_root": str(ws),
        "work_intake_exec_path": report_rel,
        "work_intake_exec_md_path": res.get("work_intake_exec_md_path") if isinstance(res, dict) else None,
        "applied_count": res.get("applied_count") if isinstance(res, dict) else 0,
        "planned_count": res.get("planned_count") if isinstance(res, dict) else 0,
        "idle_count": res.get("idle_count") if isinstance(res, dict) else 0,
        "entries_count": res.get("entries_count") if isinstance(res, dict) else 0,
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: work-intake-exec-ticket (safe-only, workspace-only)")
        print(f"workspace_root={payload.get('workspace_root')}")
        print("RESULT:")
        print(
            f"status={payload.get('status')} applied={payload.get('applied_count')} "
            f"planned={payload.get('planned_count')} idle={payload.get('idle_count')}"
        )
        print("EVIDENCE:")
        for p in [payload.get("work_intake_exec_path"), payload.get("work_intake_exec_md_path")]:
            if p:
                print(str(p))
        print("ACTIONS:")
        if entries:
            for item in entries[:5]:
                if not isinstance(item, dict):
                    continue
                print(f"{item.get('intake_id')} status={item.get('status')} action={item.get('action_kind')}")
        else:
            print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_manual_request_submit(args: argparse.Namespace) -> int:
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

    text = str(args.text or "")
    if args.text_file:
        text_path = Path(str(args.text_file))
        text_path = (root / text_path).resolve() if not text_path.is_absolute() else text_path.resolve()
        if not text_path.exists():
            warn("FAIL error=TEXT_FILE_MISSING")
            return 2
        text = text_path.read_text(encoding="utf-8")

    payload_in: dict[str, Any] = {}
    if args.in_json:
        in_path = Path(str(args.in_json))
        in_path = (root / in_path).resolve() if not in_path.is_absolute() else in_path.resolve()
        if not in_path.exists():
            warn("FAIL error=INPUT_JSON_MISSING")
            return 2
        try:
            payload_in = json.loads(in_path.read_text(encoding="utf-8"))
        except Exception:
            warn("FAIL error=INPUT_JSON_INVALID")
            return 2

    artifact_type = str(args.artifact_type or payload_in.get("artifact_type") or "")
    domain = str(args.domain or payload_in.get("domain") or "")
    kind = str(args.kind or payload_in.get("kind") or "unspecified")
    impact_scope = str(args.impact_scope or payload_in.get("impact_scope") or "workspace-only")
    requires_core_change = payload_in.get("requires_core_change")
    if args.requires_core_change is not None:
        requires_core_change = bool(args.requires_core_change)
    tenant_id = str(args.tenant_id or payload_in.get("tenant_id") or "") or None
    source_type = str(args.source_type or (payload_in.get("source") or {}).get("type") or "human")
    source_channel = str(args.source_channel or (payload_in.get("source") or {}).get("channel") or "") or None
    source_user_id = str(args.source_user_id or (payload_in.get("source") or {}).get("user_id") or "") or None

    if not text:
        text = str(payload_in.get("text") or "")
    if not text:
        warn("FAIL error=TEXT_REQUIRED")
        return 2
    if not artifact_type or not domain:
        warn("FAIL error=ARTIFACT_TYPE_DOMAIN_REQUIRED")
        return 2

    attachments = payload_in.get("attachments") if isinstance(payload_in.get("attachments"), list) else []
    if args.attachments_json:
        try:
            attachments = json.loads(str(args.attachments_json))
        except Exception:
            attachments = []
    constraints = payload_in.get("constraints") if isinstance(payload_in.get("constraints"), dict) else {}
    if args.constraints_json:
        try:
            constraints = json.loads(str(args.constraints_json))
        except Exception:
            constraints = constraints

    tags = payload_in.get("tags") if isinstance(payload_in.get("tags"), list) else []
    if args.tags:
        tags = [t for t in str(args.tags).split(",") if t.strip()]

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError:
        warn("FAIL error=INVALID_DRY_RUN")
        return 2

    from src.ops.manual_request_cli import submit_manual_request

    res = submit_manual_request(
        workspace_root=ws,
        text=text,
        artifact_type=artifact_type,
        domain=domain,
        kind=kind,
        impact_scope=impact_scope,
        tenant_id=tenant_id,
        source_type=source_type,
        source_channel=source_channel,
        source_user_id=source_user_id,
        attachments=attachments if isinstance(attachments, list) else None,
        constraints=constraints if isinstance(constraints, dict) else None,
        requires_core_change=requires_core_change if isinstance(requires_core_change, bool) else None,
        tags=tags if isinstance(tags, list) else None,
        dry_run=bool(dry_run),
    )
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "IDLE"} else 2


def cmd_context_pack_build(args: argparse.Namespace) -> int:
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

    request_id = str(args.request_id or "").strip() or None
    mode = str(args.mode or "summary").strip().lower()
    if mode not in {"summary", "detail"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    from src.ops.context_pack_router import build_context_pack

    res = build_context_pack(workspace_root=ws, request_id=request_id, mode=mode)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_context_pack_route(args: argparse.Namespace) -> int:
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

    pack_arg = str(args.context_pack or "").strip()
    context_pack_path = None
    if pack_arg:
        pack_path = Path(pack_arg)
        pack_path = (ws / pack_path).resolve() if not pack_path.is_absolute() else pack_path.resolve()
        context_pack_path = pack_path

    from src.ops.context_pack_router import build_context_pack, route_context_pack

    if context_pack_path is None and args.request_id:
        build_res = build_context_pack(workspace_root=ws, request_id=str(args.request_id), mode="detail")
        pack_rel = build_res.get("context_pack_path") if isinstance(build_res, dict) else None
        if isinstance(pack_rel, str) and pack_rel:
            context_pack_path = (ws / pack_rel).resolve()

    res = route_context_pack(workspace_root=ws, context_pack_path=context_pack_path)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


def cmd_context_router_check(args: argparse.Namespace) -> int:
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

    chat = parse_reaper_bool(str(args.chat))
    detail = parse_reaper_bool(str(args.detail))

    manual_request_id = str(args.request_id or "").strip() or None
    manual_submit_res = None
    if args.text or args.in_json or args.text_file:
        submit_ns = argparse.Namespace(
            workspace_root=str(ws),
            text=args.text,
            text_file=args.text_file,
            in_json=args.in_json,
            artifact_type=args.artifact_type,
            domain=args.domain,
            kind=args.kind,
            impact_scope=args.impact_scope,
            requires_core_change=args.requires_core_change,
            tenant_id=args.tenant_id,
            source_type=args.source_type,
            source_channel=args.source_channel,
            source_user_id=args.source_user_id,
            attachments_json=args.attachments_json,
            constraints_json=args.constraints_json,
            tags=args.tags,
            dry_run=args.dry_run,
        )
        buf = StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            cmd_manual_request_submit(submit_ns)
        try:
            manual_submit_res = json.loads(buf.getvalue().strip() or "{}")
        except Exception:
            manual_submit_res = None
        if isinstance(manual_submit_res, dict) and isinstance(manual_submit_res.get("request_id"), str):
            manual_request_id = str(manual_submit_res.get("request_id"))

    from src.ops.context_pack_router import build_context_pack, route_context_pack
    from src.ops.work_intake_from_sources import run_work_intake_build
    from src.ops.system_status_report import run_system_status

    build_res = build_context_pack(workspace_root=ws, request_id=manual_request_id, mode="summary")
    pack_rel = build_res.get("context_pack_path") if isinstance(build_res, dict) else None
    pack_path = (ws / pack_rel).resolve() if isinstance(pack_rel, str) and pack_rel else None
    route_res = route_context_pack(workspace_root=ws, context_pack_path=pack_path)

    intake_res = run_work_intake_build(workspace_root=ws)
    work_intake_path = intake_res.get("work_intake_path") if isinstance(intake_res, dict) else None
    intake_obj: dict[str, Any] = {}
    if isinstance(work_intake_path, str) and work_intake_path:
        intake_path_abs = (ws / work_intake_path).resolve()
        try:
            intake_obj = json.loads(intake_path_abs.read_text(encoding="utf-8"))
        except Exception:
            intake_obj = {}

    sys_res = run_system_status(workspace_root=ws, core_root=root, dry_run=False)
    sys_out = sys_res.get("out_json") if isinstance(sys_res, dict) else None
    sys_rel = None
    if isinstance(sys_out, str):
        sys_rel = Path(sys_out).resolve()
        try:
            sys_rel = sys_rel.relative_to(ws)
        except Exception:
            sys_rel = None

    status = str(route_res.get("status") or "WARN")
    error_code = route_res.get("error_code") if isinstance(route_res, dict) else None

    plan_policy = intake_obj.get("plan_policy") if isinstance(intake_obj.get("plan_policy"), str) else "optional"
    items = intake_obj.get("items") if isinstance(intake_obj.get("items"), list) else []
    if plan_policy == "required" and items:
        plan_dir = ws / ".cache" / "reports" / "chg"
        plans = list(plan_dir.glob("CHG-INTAKE-*.plan.json")) if plan_dir.exists() else []
        if not plans:
            status = "IDLE"
            error_code = "NO_PLAN_FOUND"

    payload = {
        "status": status,
        "error_code": error_code,
        "workspace_root": str(ws),
        "request_id": manual_request_id,
        "context_pack_path": pack_rel,
        "context_router_result_path": str(Path(".cache") / "reports" / "context_pack_router_result.v1.json"),
        "work_intake_path": work_intake_path,
        "system_status_path": str(sys_rel) if isinstance(sys_rel, Path) else None,
        "notes": ["PROGRAM_LED=true"],
    }

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: manual-request-submit + context-pack-build + context-pack-route + work-intake-check + system-status")
        print(f"workspace_root={payload.get('workspace_root')}")
        if manual_request_id:
            print(f"request_id={manual_request_id}")
        print("RESULT:")
        print(f"status={status} bucket={route_res.get('bucket')} action={route_res.get('action')}")
        if error_code:
            print(f"error_code={error_code}")
        print("EVIDENCE:")
        for p in [
            manual_submit_res.get("stored_path") if isinstance(manual_submit_res, dict) else None,
            pack_rel,
            payload.get("context_router_result_path"),
            work_intake_path,
            payload.get("system_status_path"),
        ]:
            if p:
                print(str(p))
        print("ACTIONS:")
        next_actions = route_res.get("next_actions") if isinstance(route_res.get("next_actions"), list) else []
        if not detail:
            next_actions = next_actions[:5]
        if next_actions:
            print("\n".join([str(x) for x in next_actions]))
        else:
            print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu goster / Duraklat")

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN", "IDLE"} else 2


def cmd_layer_boundary_check(args: argparse.Namespace) -> int:
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

    mode = str(args.mode).strip().lower() if args.mode else "report"
    if mode not in {"report", "strict"}:
        warn("FAIL error=INVALID_MODE")
        return 2

    chat = parse_reaper_bool(str(args.chat))

    from src.ops.layer_boundary_check import run_layer_boundary_check

    res = run_layer_boundary_check(workspace_root=ws, mode=mode)
    if chat:
        print("PREVIEW:")
        print(f"PROGRAM-LED: layer-boundary-check mode={mode}; user_command=false")
        print(f"workspace_root={res.get('workspace_root')}")
        print("RESULT:")
        print(f"status={res.get('status')} would_block={res.get('would_block_count', 0)}")
        print("EVIDENCE:")
        for p in res.get("evidence_paths", []):
            print(str(p))
        print("ACTIONS:")
        if int(res.get("would_block_count", 0)) > 0:
            print("review_would_block_paths")
        else:
            print("no_actions")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2


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

    from src.ops.commands.extension_cmds import register_extension_subcommands as _register_extension

    _register_extension(parent)

    ap_int = parent.add_parser("integrity-verify", help="Run integrity verify (snapshot + verify-on-read).")
    ap_int.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_int.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_int.set_defaults(func=cmd_integrity_verify)

    ap_intake = parent.add_parser("work-intake-build", help="Build work intake from gaps + PDCA (workspace).")
    ap_intake.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake.set_defaults(func=cmd_work_intake_build)

    ap_intake_check = parent.add_parser("work-intake-check", help="Build + summarize work intake (program-led).")
    ap_intake_check.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_check.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_intake_check.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_intake_check.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_intake_check.set_defaults(func=cmd_work_intake_check)

    ap_intake_exec = parent.add_parser("work-intake-exec-ticket", help="Execute TICKET intake items (safe-only, workspace-only).")
    ap_intake_exec.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_intake_exec.add_argument("--limit", default="3", help="Max items to execute (default: 3).")
    ap_intake_exec.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_intake_exec.set_defaults(func=cmd_work_intake_exec_ticket)

    ap_manual = parent.add_parser("manual-request-submit", help="Submit manual request (workspace-scoped, program-led).")
    ap_manual.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_manual.add_argument("--text", default="", help="Request text (short).")
    ap_manual.add_argument("--text-file", default="", help="Path to request text file.")
    ap_manual.add_argument("--in", dest="in_json", default="", help="Path to JSON input payload (optional).")
    ap_manual.add_argument("--artifact-type", default="", help="Artifact type (required if --in not provided).")
    ap_manual.add_argument("--domain", default="", help="Domain label (required if --in not provided).")
    ap_manual.add_argument(
        "--kind",
        default="unspecified",
        help="support|question|minor_fix|feature|refactor|new_project|strategy|multi-quarter|context-router|doc-fix|note|unspecified",
    )
    ap_manual.add_argument(
        "--impact-scope",
        default="workspace-only",
        help="doc-only|workspace-only|core-change|external-change (default: workspace-only)",
    )
    ap_manual.add_argument("--requires-core-change", action="store_true", help="Flag: requires core change.")
    ap_manual.add_argument("--tenant-id", default="", help="Optional tenant id.")
    ap_manual.add_argument("--source-type", default="human", help="human|llm|system|api|webhook|ui|chat")
    ap_manual.add_argument("--source-channel", default="", help="Optional source channel.")
    ap_manual.add_argument("--source-user-id", default="", help="Optional source user id.")
    ap_manual.add_argument("--attachments-json", default="", help="JSON array for attachments (optional).")
    ap_manual.add_argument("--constraints-json", default="", help="JSON object for constraints (optional).")
    ap_manual.add_argument("--tags", default="", help="Comma-separated tags (optional).")
    ap_manual.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_manual.set_defaults(func=cmd_manual_request_submit)

    ap_pack = parent.add_parser("context-pack-build", help="Build context pack (pointer graph).")
    ap_pack.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_pack.add_argument("--request-id", default="", help="Manual request id (optional).")
    ap_pack.add_argument("--mode", default="summary", help="summary|detail (default: summary).")
    ap_pack.set_defaults(func=cmd_context_pack_build)

    ap_route = parent.add_parser("context-pack-route", help="Route context pack to bucket/action.")
    ap_route.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_route.add_argument("--context-pack", default="", help="Path to context pack JSON (optional).")
    ap_route.add_argument("--request-id", default="", help="Manual request id (optional).")
    ap_route.set_defaults(func=cmd_context_pack_route)

    ap_router = parent.add_parser("context-router-check", help="Single gate: submit + build + route + intake + status.")
    ap_router.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_router.add_argument("--request-id", default="", help="Manual request id (optional).")
    ap_router.add_argument("--text", default="", help="Request text (short).")
    ap_router.add_argument("--text-file", default="", help="Path to request text file.")
    ap_router.add_argument("--in", dest="in_json", default="", help="Path to JSON input payload (optional).")
    ap_router.add_argument("--artifact-type", default="", help="Artifact type (required if --in not provided).")
    ap_router.add_argument("--domain", default="", help="Domain label (required if --in not provided).")
    ap_router.add_argument(
        "--kind",
        default="unspecified",
        help="support|question|minor_fix|feature|refactor|new_project|strategy|multi-quarter|context-router|doc-fix|note|unspecified",
    )
    ap_router.add_argument(
        "--impact-scope",
        default="workspace-only",
        help="doc-only|workspace-only|core-change|external-change (default: workspace-only)",
    )
    ap_router.add_argument("--requires-core-change", action="store_true", help="Flag: requires core change.")
    ap_router.add_argument("--tenant-id", default="", help="Optional tenant id.")
    ap_router.add_argument("--source-type", default="human", help="human|llm|system|api|webhook|ui|chat")
    ap_router.add_argument("--source-channel", default="", help="Optional source channel.")
    ap_router.add_argument("--source-user-id", default="", help="Optional source user id.")
    ap_router.add_argument("--attachments-json", default="", help="JSON array for attachments (optional).")
    ap_router.add_argument("--constraints-json", default="", help="JSON object for constraints (optional).")
    ap_router.add_argument("--tags", default="", help="Comma-separated tags (optional).")
    ap_router.add_argument("--dry-run", default="false", help="true|false (default: false).")
    ap_router.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_router.add_argument("--detail", default="false", help="true|false (default: false).")
    ap_router.set_defaults(func=cmd_context_router_check)

    ap_layer = parent.add_parser("layer-boundary-check", help="Check layer boundary constraints (report|strict).")
    ap_layer.add_argument("--workspace-root", required=True, help="Workspace root path.")
    ap_layer.add_argument("--mode", default="report", help="report|strict (default: report).")
    ap_layer.add_argument("--chat", default="false", help="true|false (default: false).")
    ap_layer.set_defaults(func=cmd_layer_boundary_check)

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
