from __future__ import annotations

import argparse
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from src.ops.commands.common import repo_root, run_step, warn
from src.ops.reaper import (
    compute_reaper_report,
    parse_bool as parse_reaper_bool,
    parse_iso8601 as parse_reaper_iso,
    write_report as write_reaper_report,
)


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

    report_path = _policy_check_generate_report(root=root, outdir=outdir)
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
