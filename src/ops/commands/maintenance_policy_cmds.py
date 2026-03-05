from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from src.ops.commands.common import repo_root, run_step, warn
from src.ops.reaper import (
    compute_reaper_report,
    list_critical_cache_files,
    parse_bool as parse_reaper_bool,
    parse_iso8601 as parse_reaper_iso,
    write_report as write_reaper_report,
)


def _rel_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _snapshot_critical_files(*, root: Path, files: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fp in sorted(files, key=lambda p: _rel_path(root, p)):
        rel = _rel_path(root, fp)
        row: dict[str, object] = {"path": rel, "exists": bool(fp.exists())}
        if fp.exists():
            row["bytes"] = int(fp.stat().st_size)
            row["sha256"] = _sha256_file(fp)
        rows.append(row)
    return rows


def _validate_critical_snapshot(*, root: Path, pre_rows: list[dict[str, object]]) -> dict[str, object]:
    missing_paths: list[str] = []
    changed_paths: list[str] = []
    checked = 0
    for row in pre_rows:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "").strip()
        if not rel:
            continue
        if row.get("exists") is not True:
            continue
        checked += 1
        current = (root / rel).resolve()
        if not current.exists():
            missing_paths.append(rel)
            continue
        before_sha = str(row.get("sha256") or "").strip()
        if before_sha:
            after_sha = _sha256_file(current)
            if after_sha != before_sha:
                changed_paths.append(rel)
    return {
        "status": "PASS" if not missing_paths else "FAIL",
        "checked": checked,
        "missing_count": len(missing_paths),
        "changed_count": len(changed_paths),
        "missing_paths": missing_paths,
        "changed_paths": changed_paths,
    }


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

    guard_pre_path = root / ".cache" / "reports" / "reaper_cleanup_pre_snapshot.v1.json"
    guard_post_path = root / ".cache" / "reports" / "reaper_cleanup_post_validate.v1.json"
    pre_rows: list[dict[str, object]] = []
    if not dry_run:
        critical_files = list_critical_cache_files(root=root)
        pre_rows = _snapshot_critical_files(root=root, files=critical_files)
        guard_pre_payload = {
            "version": "v1",
            "generated_at": now.isoformat(),
            "status": "OK",
            "critical_files_count": len(pre_rows),
            "critical_files": pre_rows,
            "notes": [
                "CLEANUP_GUARD=true",
                "PHASE=PRE_SNAPSHOT",
                "NO_NETWORK=true",
            ],
        }
        write_reaper_report(guard_pre_path, guard_pre_payload)

    report = compute_reaper_report(root=root, dry_run=dry_run, now=now)

    guard_status = "SKIPPED"
    if not dry_run:
        post_result = _validate_critical_snapshot(root=root, pre_rows=pre_rows)
        guard_status = str(post_result.get("status") or "FAIL")
        guard_post_payload = {
            "version": "v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": guard_status,
            "pre_snapshot_path": _rel_path(root, guard_pre_path),
            "post_validate": post_result,
            "notes": [
                "CLEANUP_GUARD=true",
                "PHASE=POST_VALIDATE",
                "NO_NETWORK=true",
            ],
        }
        write_reaper_report(guard_post_path, guard_post_payload)
        report["guard"] = {
            "status": guard_status,
            "pre_snapshot_path": _rel_path(root, guard_pre_path),
            "post_validate_path": _rel_path(root, guard_post_path),
            "critical_files_count": len(pre_rows),
            "missing_count": int(post_result.get("missing_count") or 0),
            "changed_count": int(post_result.get("changed_count") or 0),
        }
    else:
        report["guard"] = {
            "status": "DRY_RUN",
            "pre_snapshot_path": "",
            "post_validate_path": "",
            "critical_files_count": 0,
            "missing_count": 0,
            "changed_count": 0,
        }

    if args.out:
        out_path = Path(str(args.out))
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
        write_reaper_report(out_path, report)

    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    dlq = report.get("dlq") if isinstance(report.get("dlq"), dict) else {}
    cache = report.get("cache") if isinstance(report.get("cache"), dict) else {}
    guard = report.get("guard") if isinstance(report.get("guard"), dict) else {}

    print(
        "reaper "
        + f"dry_run={bool(report.get('dry_run'))} "
        + f"evidence_candidates={int(evidence.get('candidates', 0))} "
        + f"dlq_candidates={int(dlq.get('candidates', 0))} "
        + f"cache_candidates={int(cache.get('candidates', 0))} "
        + f"deleted_total={int(evidence.get('deleted', 0)) + int(dlq.get('deleted', 0)) + int(cache.get('deleted', 0))} "
        + f"guard_status={str(guard.get('status') or 'UNKNOWN')}"
    )
    if not dry_run and str(guard.get("status") or "FAIL") != "PASS":
        warn("FAIL error=REAPER_GUARD_POST_VALIDATE")
        return 2
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


def _policy_check_generate_report(
    *,
    root: Path,
    outdir: Path,
    north_star_subject_plan_contract: dict[str, object],
) -> Path:
    report_path = outdir / "POLICY_REPORT.md"
    try:
        from src.ops.policy_report import generate_policy_report_markdown

        md = generate_policy_report_markdown(
            in_dir=outdir,
            root=root,
            north_star_subject_plan_contract=north_star_subject_plan_contract,
        )
        report_path.write_text(md, encoding="utf-8")
    except Exception:
        report_path.write_text("# Policy Check Report\n\n(Report generation failed.)\n", encoding="utf-8")
    return report_path


def _policy_check_collect_deprecation_warnings(root: Path) -> list[dict[str, object]]:
    try:
        from src.ops.policy_report import collect_policy_deprecation_warnings
    except Exception:
        return []
    try:
        items = collect_policy_deprecation_warnings(root)
    except Exception:
        return []
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def _policy_check_collect_north_star_subject_plan_contract(root: Path) -> dict[str, object]:
    try:
        from src.ops.policy_report import collect_north_star_subject_plan_contract_status
    except Exception:
        return {
            "schema_path": "schemas/north-star-subject-plan.schema.v1.json",
            "schema_exists": False,
            "schema_valid": False,
            "schema_id": "",
            "schema_error": "import_failed",
        }
    try:
        payload = collect_north_star_subject_plan_contract_status(root)
    except Exception:
        return {
            "schema_path": "schemas/north-star-subject-plan.schema.v1.json",
            "schema_exists": False,
            "schema_valid": False,
            "schema_id": "",
            "schema_error": "collect_failed",
        }
    if not isinstance(payload, dict):
        return {
            "schema_path": "schemas/north-star-subject-plan.schema.v1.json",
            "schema_exists": False,
            "schema_valid": False,
            "schema_id": "",
            "schema_error": "invalid_payload",
        }
    return payload


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
    try:
        max_deprecation_warnings = int(str(args.max_deprecation_warnings))
    except Exception:
        warn("FAIL error=INVALID_MAX_DEPRECATION_WARNINGS")
        return 2
    if max_deprecation_warnings < -1:
        warn("FAIL error=INVALID_MAX_DEPRECATION_WARNINGS")
        return 2

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

    rc, _, _ = run_step(
        root,
        [
            sys.executable,
            str(root / "ci" / "policy_diff_sim.py"),
            "--baseline",
            baseline,
            "--fixtures",
            fixtures,
            "--evidence",
            evidence,
            "--source",
            source,
            "--out",
            str(diff_out),
        ],
        stage="POLICY_DIFF_SIM",
    )
    if rc != 0:
        return 2

    north_star_contract = _policy_check_collect_north_star_subject_plan_contract(root)

    report_path = _policy_check_generate_report(
        root=root,
        outdir=outdir,
        north_star_subject_plan_contract=north_star_contract,
    )
    freshness_report_rel = ".cache/reports/model_catalog_freshness.v1.json"
    freshness_status = "SKIP"
    freshness_overall = ""
    freshness_error_code = ""
    try:
        from src.ops.model_catalog_freshness import run_model_catalog_freshness

        freshness_out = (root / freshness_report_rel).resolve()
        freshness_res = run_model_catalog_freshness(repo_root=root, out_path=freshness_out)
        freshness_status = str(freshness_res.get("status") or "FAIL")
        freshness_overall = str(freshness_res.get("overall_status") or "")
        freshness_error_code = str(freshness_res.get("error_code") or "")
        rel = freshness_res.get("report_path")
        if isinstance(rel, str) and rel.strip():
            freshness_report_rel = rel
    except Exception:
        freshness_status = "FAIL"
        freshness_error_code = "MODEL_CATALOG_FRESHNESS_EXCEPTION"

    report_rel = report_path.resolve().relative_to(root.resolve()).as_posix()
    sim_rel = sim_out.resolve().relative_to(root.resolve()).as_posix()
    diff_rel = diff_out.resolve().relative_to(root.resolve()).as_posix()

    allow, suspend, block, invalid = _policy_check_read_sim_counts(sim_out)
    diff_nonzero = _policy_check_read_diff_nonzero(diff_out)
    deprecation_warnings = _policy_check_collect_deprecation_warnings(root)
    deprecation_warning_count = len(deprecation_warnings)
    deprecation_warning_codes = sorted(
        {
            str(item.get("code"))
            for item in deprecation_warnings
            if isinstance(item.get("code"), str) and str(item.get("code")).strip()
        }
    )
    gate_enabled = max_deprecation_warnings >= 0
    gate_exceeded = gate_enabled and deprecation_warning_count > max_deprecation_warnings

    if gate_exceeded:
        status = "FAIL"
    elif diff_nonzero == 0 and block == 0 and invalid == 0:
        status = "OK"
    else:
        status = "WARN"

    summary = {
        "status": status,
        "allow": allow,
        "suspend": suspend,
        "block_unknown_intent": block,
        "invalid_envelope": invalid,
        "diff_nonzero": diff_nonzero,
        "deprecation_warning_count": deprecation_warning_count,
        "deprecation_warning_codes": deprecation_warning_codes,
        "max_deprecation_warnings": max_deprecation_warnings,
        "deprecation_gate_enabled": gate_enabled,
        "deprecation_gate_exceeded": gate_exceeded,
        "north_star_subject_plan_contract_schema": str(
            north_star_contract.get("schema_path") or "schemas/north-star-subject-plan.schema.v1.json"
        ),
        "north_star_subject_plan_contract_schema_exists": bool(north_star_contract.get("schema_exists", False)),
        "north_star_subject_plan_contract_schema_valid": bool(north_star_contract.get("schema_valid", False)),
        "north_star_subject_plan_contract_schema_id": str(north_star_contract.get("schema_id") or ""),
        "north_star_subject_plan_contract_schema_error": str(north_star_contract.get("schema_error") or ""),
        "model_catalog_freshness_status": freshness_status,
        "model_catalog_freshness_overall": freshness_overall,
        "model_catalog_freshness_error_code": freshness_error_code,
        "model_catalog_freshness_report": freshness_report_rel,
        "sim_report": sim_rel,
        "policy_diff": diff_rel,
        "report": report_rel,
    }
    if gate_exceeded:
        summary["error_code"] = "DEPRECATION_WARNING_THRESHOLD_EXCEEDED"

    out_buf = StringIO()
    with redirect_stdout(out_buf), redirect_stderr(out_buf):
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    print(out_buf.getvalue().strip())
    return 2 if gate_exceeded else 0
