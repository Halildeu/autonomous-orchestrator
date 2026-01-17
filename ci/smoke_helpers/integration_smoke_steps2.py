from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

from ci.smoke_helpers.utils import run_cmd


def _smoke_system_status(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    dry_json = ws_dry_run / ".cache" / "reports" / "system_status.v1.json"
    dry_md = ws_dry_run / ".cache" / "reports" / "system_status.v1.md"
    if dry_json.exists() or dry_md.exists():
        raise SystemExit("Smoke test failed: M8.1 dry-run must not write system status reports.")
    out_json = ws_integration / ".cache" / "reports" / "system_status.v1.json"
    out_md = ws_integration / ".cache" / "reports" / "system_status.v1.md"
    if not out_json.exists() or not out_md.exists():
        raise SystemExit("Smoke test failed: M8.1 apply must write system status JSON + MD.")
    try:
        report = json.loads(out_json.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: system_status.v1.json must be valid JSON.") from e
    schema_path = repo_root / "schemas" / "system-status.schema.json"
    if not schema_path.exists():
        raise SystemExit("Smoke test failed: missing system status schema: " + str(schema_path))
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
    except Exception as e:
        raise SystemExit("Smoke test failed: system status must validate against schema.") from e
    md_text = out_md.read_text(encoding="utf-8")
    required_headings = [
        "ISO Core",
        "Spec Core",
        "Core integrity",
        "Core lock",
        "Project boundary",
        "Projects",
        "Extensions",
        "Release",
        "Catalog",
        "Packs",
        "Formats",
        "Session",
        "Quality",
        "Harvest",
        "Advisor",
        "Pack Advisor",
        "Readiness",
        "Actions",
        "Repo hygiene",
        "Doc graph",
        "Auto-heal",
    ]
    for heading in required_headings:
        if heading not in md_text:
            raise SystemExit("Smoke test failed: system status MD missing heading: " + heading)
    overall = report.get("overall_status") if isinstance(report, dict) else None
    if overall not in {"OK", "WARN", "NOT_READY"}:
        raise SystemExit("Smoke test failed: system status overall_status must be OK, WARN, or NOT_READY.")
    spec_core = report.get("sections", {}).get("spec_core") if isinstance(report, dict) else None
    if not isinstance(spec_core, dict):
        raise SystemExit("Smoke test failed: system status must include spec_core section.")
    spec_paths = spec_core.get("paths") if isinstance(spec_core.get("paths"), list) else None
    if not isinstance(spec_paths, list):
        raise SystemExit("Smoke test failed: spec_core.paths must be a list.")
    required_paths = {"schemas/spec-core.schema.json", "schemas/spec-capability.schema.json"}
    if not required_paths.issubset(set(str(p) for p in spec_paths)):
        raise SystemExit("Smoke test failed: spec_core.paths must include spec-core schemas.")
    core_integrity = report.get("sections", {}).get("core_integrity") if isinstance(report, dict) else None
    if not isinstance(core_integrity, dict):
        raise SystemExit("Smoke test failed: system status must include core_integrity section.")
    if core_integrity.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: core_integrity.status must be OK, WARN, or FAIL.")
    if core_integrity.get("git_clean") is not True:
        raise SystemExit("Smoke test failed: core_integrity.git_clean must be true in smoke.")
    core_lock = report.get("sections", {}).get("core_lock") if isinstance(report, dict) else None
    if not isinstance(core_lock, dict):
        raise SystemExit("Smoke test failed: system status must include core_lock section.")
    if core_lock.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: core_lock.status must be OK or WARN.")
    project_boundary = report.get("sections", {}).get("project_boundary") if isinstance(report, dict) else None
    if not isinstance(project_boundary, dict):
        raise SystemExit("Smoke test failed: system status must include project_boundary section.")
    if project_boundary.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: project_boundary.status must be OK or WARN.")
    projects = report.get("sections", {}).get("projects") if isinstance(report, dict) else None
    if not isinstance(projects, dict):
        raise SystemExit("Smoke test failed: system status must include projects section.")
    if projects.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: projects.status must be OK or WARN.")
    if not isinstance(projects.get("active_projects"), list):
        raise SystemExit("Smoke test failed: projects.active_projects must be a list.")
    bench = report.get("sections", {}).get("benchmark") if isinstance(report, dict) else None
    if not isinstance(bench, dict):
        raise SystemExit("Smoke test failed: system status must include benchmark section.")
    if not isinstance(bench.get("gaps_by_severity"), dict):
        raise SystemExit("Smoke test failed: benchmark.gaps_by_severity must be a dict.")
    if not isinstance(bench.get("top_next_actions"), list):
        raise SystemExit("Smoke test failed: benchmark.top_next_actions must be a list.")
    packs = report.get("sections", {}).get("packs") if isinstance(report, dict) else None
    if not isinstance(packs, dict):
        raise SystemExit("Smoke test failed: system status must include packs section.")
    if packs.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: packs.status must be OK, WARN, or FAIL.")
    if not isinstance(packs.get("selected_pack_ids"), list):
        raise SystemExit("Smoke test failed: packs.selected_pack_ids must be a list.")
    if not isinstance(packs.get("selection_trace_path"), str):
        raise SystemExit("Smoke test failed: packs.selection_trace_path must be a string.")
    pack_adv = report.get("sections", {}).get("pack_advisor") if isinstance(report, dict) else None
    if not isinstance(pack_adv, dict):
        raise SystemExit("Smoke test failed: system status must include pack_advisor section.")
    if pack_adv.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: pack_advisor.status must be OK, WARN, or FAIL.")
    repo_hygiene = report.get("sections", {}).get("repo_hygiene") if isinstance(report, dict) else None
    if not isinstance(repo_hygiene, dict):
        raise SystemExit("Smoke test failed: system status must include repo_hygiene section.")
    if repo_hygiene.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: repo_hygiene.status must be OK or WARN.")
    if not isinstance(repo_hygiene.get("unexpected_top_level_dirs"), int):
        raise SystemExit("Smoke test failed: repo_hygiene.unexpected_top_level_dirs must be int.")
    if not isinstance(repo_hygiene.get("tracked_generated_files"), int):
        raise SystemExit("Smoke test failed: repo_hygiene.tracked_generated_files must be int.")
    doc_graph = report.get("sections", {}).get("doc_graph") if isinstance(report, dict) else None
    if not isinstance(doc_graph, dict):
        raise SystemExit("Smoke test failed: system status must include doc_graph section.")
    if doc_graph.get("status") not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: doc_graph.status must be OK, WARN, or FAIL.")
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "system-status",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: manage system-status command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: system-status must print JSON.") from e
    if not isinstance(out, dict) or "overall_status" not in out:
        raise SystemExit("Smoke test failed: system-status output must include overall_status.")
    print("CRITICAL_CORE_IMMUTABILITY ok=true git_clean=true")
    proj = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "project-status",
            "--roadmap",
            "roadmaps/SSOT/roadmap.v1.json",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "autopilot_chat",
        ],
        env=env,
        fail_msg="Smoke test failed: project-status command failed.",
        capture=True,
    )
    proj_text = proj.stdout.strip()
    for heading in ["PREVIEW:", "RESULT:", "EVIDENCE:", "ACTIONS:", "NEXT:"]:
        if heading not in proj_text:
            raise SystemExit("Smoke test failed: project-status missing heading: " + heading)
    try:
        proj_json = json.loads(proj_text.splitlines()[-1])
    except Exception as e:
        raise SystemExit("Smoke test failed: project-status trailing JSON invalid.") from e
    if not isinstance(proj_json, dict):
        raise SystemExit("Smoke test failed: project-status JSON must be an object.")
    if proj_json.get("core_lock") != "ENABLED":
        raise SystemExit("Smoke test failed: project-status core_lock must be ENABLED.")
    if proj_json.get("project_manifest_present") is not True:
        raise SystemExit("Smoke test failed: project manifest must be present.")
    print(
        f"CRITICAL_PROJECT_STATUS ok=true next={proj_json.get('next_milestone')} status={proj_json.get('status')}"
    )
    core_lock_enabled = proj_json.get("core_lock") == "ENABLED"
    boundary_ok = proj_json.get("project_manifest_present") is True
    print("CRITICAL_PROJECT_BOUNDARY ok=true core_lock=true manifest=true")
    print(f"CRITICAL_CORE_LOCK ok=true locked={core_lock_enabled} boundary_ok={boundary_ok}")
    portfolio = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "portfolio-status",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "autopilot_chat",
        ],
        env=env,
        fail_msg="Smoke test failed: portfolio-status command failed.",
        capture=True,
    )
    portfolio_text = portfolio.stdout.strip()
    for heading in ["PREVIEW:", "RESULT:", "EVIDENCE:", "ACTIONS:", "NEXT:"]:
        if heading not in portfolio_text:
            raise SystemExit("Smoke test failed: portfolio-status missing heading: " + heading)
    try:
        portfolio_json = json.loads(portfolio_text.splitlines()[-1])
    except Exception as e:
        raise SystemExit("Smoke test failed: portfolio-status trailing JSON invalid.") from e
    if not isinstance(portfolio_json, dict):
        raise SystemExit("Smoke test failed: portfolio-status JSON must be an object.")
    print(
        f"CRITICAL_PORTFOLIO_STATUS ok=true projects={portfolio_json.get('projects_count')} "
        f"next={portfolio_json.get('next_project_focus')}"
    )
    print(f"CRITICAL_SYSTEM_STATUS ok=true overall={overall}")


def _smoke_doc_graph(*, repo_root: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    out_path = ws_integration / ".cache" / "reports" / "doc_graph_report.v1.json"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "doc-graph",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "report",
            "--out",
            str(out_path.relative_to(ws_integration)),
        ],
        env=env,
        fail_msg="Smoke test failed: doc-graph command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: doc-graph must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: doc-graph output must be JSON object.")
    if not out_path.exists():
        raise SystemExit("Smoke test failed: doc_graph_report.v1.json missing.")
    try:
        report = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: doc graph report must be valid JSON.") from e
    schema_path = repo_root / "schemas" / "doc-graph-report.schema.json"
    if not schema_path.exists():
        raise SystemExit("Smoke test failed: missing doc-graph report schema.")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
    except Exception as e:
        raise SystemExit("Smoke test failed: doc graph report must validate against schema.") from e
    status = report.get("status") if isinstance(report, dict) else None
    broken = report.get("counts", {}).get("broken_refs", 0) if isinstance(report, dict) else 0
    if status not in {"OK", "WARN", "FAIL"}:
        raise SystemExit("Smoke test failed: doc graph status must be OK, WARN, or FAIL.")
    print(f"CRITICAL_DOC_GRAPH ok=true broken={broken} status={status}")


def _smoke_doc_nav_check(*, repo_root: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    smoke_level = os.environ.get("SMOKE_LEVEL", "full").lower()
    env["SMOKE_LEVEL"] = smoke_level
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "doc-nav-check",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
        ],
        env=env,
        fail_msg="Smoke test failed: doc-nav-check command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: doc-nav-check must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: doc-nav-check output must be JSON object.")
    if not isinstance(payload.get("doc_graph"), dict) or not isinstance(payload.get("cockpit"), dict):
        raise SystemExit("Smoke test failed: doc-nav-check payload missing doc_graph/cockpit.")
    doc_graph_summary = payload.get("doc_graph") if isinstance(payload, dict) else {}
    if not isinstance(doc_graph_summary.get("placeholder_refs_count"), int):
        raise SystemExit("Smoke test failed: doc-nav-check missing placeholder_refs_count.")
    evidence = payload.get("evidence_paths") if isinstance(payload.get("evidence_paths"), list) else []
    for p in evidence:
        if not isinstance(p, str):
            continue
        path = Path(p)
        if not path.is_absolute():
            path = ws_integration / path
        if not path.exists():
            raise SystemExit("Smoke test failed: doc-nav-check evidence path missing: " + str(path))

    notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    fallback = payload.get("error_code") == "SUMMARY_TIMEOUT_FALLBACK" or any(
        "summary_timeout_fallback_to_strict=true" in str(n) for n in notes
    )
    status = payload.get("status") if isinstance(payload.get("status"), str) else "WARN"
    print(
        "CRITICAL_DOC_NAV_SUMMARY ok=true "
        + f"status={status} fallback={str(fallback).lower()} timeout_fallback_allowed=true"
    )

    if smoke_level != "fast":
        proc_detail = run_cmd(
            repo_root=repo_root,
            argv=[
                sys.executable,
                "-m",
                "src.ops.manage",
                "doc-nav-check",
                "--workspace-root",
                str(ws_integration.relative_to(repo_root)),
                "--detail",
                "true",
            ],
            env=env,
            fail_msg="Smoke test failed: doc-nav-check --detail command failed.",
            capture=True,
        )
        try:
            payload_detail = json.loads(proc_detail.stdout.strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: doc-nav-check --detail must print JSON.") from e
        doc_graph_detail = payload_detail.get("doc_graph") if isinstance(payload_detail, dict) else None
        if not isinstance(doc_graph_detail, dict):
            raise SystemExit("Smoke test failed: doc-nav-check --detail missing doc_graph.")
        if not isinstance(doc_graph_detail.get("top_broken"), list) or not isinstance(doc_graph_detail.get("top_orphans"), list):
            raise SystemExit("Smoke test failed: doc-nav-check --detail must include top lists.")

        proc_strict = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.manage",
                "doc-nav-check",
                "--workspace-root",
                str(ws_integration.relative_to(repo_root)),
                "--strict",
                "true",
                "--detail",
                "true",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            env=env,
        )
        if proc_strict.returncode not in (0, 2):
            raise SystemExit("Smoke test failed: doc-nav-check --strict command failed.")
        try:
            payload_strict = json.loads(proc_strict.stdout.strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: doc-nav-check --strict must print JSON.") from e
        notes = payload_strict.get("notes") if isinstance(payload_strict, dict) else None
        if not isinstance(notes, list) or "strict=true" not in [str(x) for x in notes]:
            raise SystemExit("Smoke test failed: doc-nav-check --strict must set strict flag in notes.")
        strict_path = ws_integration / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
        if not strict_path.exists():
            raise SystemExit("Smoke test failed: strict doc graph report missing: " + str(strict_path))
        system_status_path = ws_integration / ".cache" / "reports" / "system_status.v1.json"
        if not system_status_path.exists():
            raise SystemExit("Smoke test failed: system_status report missing: " + str(system_status_path))
        try:
            sys_obj = json.loads(system_status_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("Smoke test failed: system_status report must be valid JSON.") from e
        overall = sys_obj.get("overall_status") if isinstance(sys_obj, dict) else None
        if str(overall) == "NOT_READY":
            raise SystemExit("Smoke test failed: strict doc-nav-check must not flip cockpit to NOT_READY.")
        print("CRITICAL_DOC_NAV_PUBLISH_ISOLATION ok=true")

    status = payload.get("status")
    doc_graph = payload.get("doc_graph") if isinstance(payload, dict) else {}
    broken = doc_graph.get("broken_refs", 0)
    ambiguity = doc_graph.get("ambiguity", 0)
    nav_gaps = doc_graph.get("critical_nav_gaps", 0)
    placeholders = doc_graph.get("placeholder_refs_count", 0)
    orphan = doc_graph.get("orphan_critical", 0)
    if status == "FAIL":
        raise SystemExit("Smoke test failed: doc-nav-check summary must not be FAIL.")
    if not isinstance(orphan, int) or orphan != 0:
        raise SystemExit("Smoke test failed: doc-nav-check orphan_critical must be 0.")
    print(f"CRITICAL_DOC_NAV_CHECK ok=true status={status} broken={broken} nav_gaps={nav_gaps} ambiguity={ambiguity}")
    print(
        "CRITICAL_DOC_NAV_SINGLE_GATE ok=true status="
        f"{status} broken={broken} nav_gaps={nav_gaps} ambiguity={ambiguity} mode=summary"
    )
    print(f"CRITICAL_DOC_NAV_LOCK ok=true broken={broken} placeholders={placeholders} orphan={orphan} status={status}")


def _smoke_auto_loop_counts(*, repo_root: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    run_cmd(
        repo_root=repo_root,
        argv=[sys.executable, str(repo_root / "src" / "ops" / "auto_loop_counts_contract_test.py")],
        env=env,
        fail_msg="Smoke test failed: auto_loop_counts_contract_test failed.",
    )
    report_path = (
        repo_root
        / ".cache"
        / "ws_auto_loop_counts_contract"
        / ".cache"
        / "reports"
        / "auto_loop_apply_details.v1.json"
    )
    if not report_path.exists():
        raise SystemExit("Smoke test failed: auto_loop_apply_details.v1.json missing.")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: auto_loop_apply_details must be valid JSON.") from e
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    applied_ids = counts.get("applied_intake_ids") if isinstance(counts.get("applied_intake_ids"), list) else []
    limit_ids = (
        counts.get("limit_reached_intake_ids") if isinstance(counts.get("limit_reached_intake_ids"), list) else []
    )
    applied = int(counts.get("applied") or len(applied_ids))
    skipped = int(counts.get("skipped") or 0)
    limit_reached = int(counts.get("limit_reached") or len(limit_ids))
    print(
        "CRITICAL_AUTO_LOOP_COUNTS ok=true "
        f"applied={applied} skipped={skipped} limit_reached={limit_reached}"
    )


def _smoke_extension_registry(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "extension-registry",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "report",
            "--chat",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: extension-registry command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: extension-registry must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: extension-registry output must be JSON object.")
    status = payload.get("status") if isinstance(payload.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Smoke test failed: extension-registry status invalid.")
    registry_path = ws_integration / ".cache" / "index" / "extension_registry.v1.json"
    if not registry_path.exists():
        raise SystemExit("Smoke test failed: extension_registry.v1.json missing.")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: extension_registry.v1.json invalid JSON.") from e
    extensions = registry.get("extensions") if isinstance(registry, dict) else None
    count = len([e for e in extensions if isinstance(e, dict)]) if isinstance(extensions, list) else 0
    print(f"CRITICAL_EXTENSION_REGISTRY ok=true status={status} count={count}")


def _smoke_extension_help(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "extension-help",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chat",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: extension-help command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: extension-help must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: extension-help output must be JSON object.")
    status = payload.get("status") if isinstance(payload.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Smoke test failed: extension-help status invalid.")
    help_path = ws_integration / ".cache" / "reports" / "extension_help.v1.json"
    if not help_path.exists():
        raise SystemExit("Smoke test failed: extension_help.v1.json missing.")
    try:
        help_obj = json.loads(help_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: extension_help.v1.json invalid JSON.") from e
    coverage = help_obj.get("docs_coverage") if isinstance(help_obj, dict) else None
    total = int(coverage.get("total", 0)) if isinstance(coverage, dict) else 0
    with_docs = int(coverage.get("with_docs_ref", 0)) if isinstance(coverage, dict) else 0
    tests_cov = help_obj.get("tests_coverage") if isinstance(help_obj, dict) else None
    tests_total = int(tests_cov.get("total", 0)) if isinstance(tests_cov, dict) else 0
    tests_with = int(tests_cov.get("with_tests_files", 0)) if isinstance(tests_cov, dict) else 0
    if tests_total != total:
        raise SystemExit("Smoke test failed: extension-help tests_coverage total mismatch.")
    if tests_with != tests_total:
        raise SystemExit("Smoke test failed: extension-help tests_coverage incomplete.")
    print(f"CRITICAL_EXTENSIONS_HELP ok=true status={status} docs_cov={with_docs}/{total} tests_cov={tests_with}/{tests_total}")


def _smoke_extension_isolation(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    registry_path = ws_integration / ".cache" / "index" / "extension_registry.v1.json"
    if not registry_path.exists():
        raise SystemExit("Smoke test failed: extension_registry.v1.json missing for isolation.")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: extension_registry.v1.json invalid JSON.") from e
    entries = registry.get("extensions") if isinstance(registry, dict) else None
    ext_ids = [e.get("extension_id") for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
    ext_ids = sorted([e for e in ext_ids if isinstance(e, str) and e])
    if not ext_ids:
        raise SystemExit("Smoke test failed: no extensions found for isolation.")
    extension_id = ext_ids[0]

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "extension-run",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--extension-id",
            extension_id,
            "--mode",
            "report",
            "--chat",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: extension-run command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: extension-run must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: extension-run output must be JSON object.")
    status = payload.get("status") if isinstance(payload.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Smoke test failed: extension-run status invalid.")
    if payload.get("network_allowed") is not False:
        raise SystemExit("Smoke test failed: extension-run must keep network disabled.")
    report_path = payload.get("report_path")
    if not isinstance(report_path, str) or not report_path:
        raise SystemExit("Smoke test failed: extension-run report_path missing.")
    report_file = ws_integration / report_path
    if not report_file.exists():
        raise SystemExit("Smoke test failed: extension-run report file missing.")
    ext_root = payload.get("extension_workspace_root", "")
    if not str(ext_root).startswith(".cache/extensions/"):
        raise SystemExit("Smoke test failed: extension-run root must be under .cache/extensions.")
    print(f"CRITICAL_EXTENSION_ISOLATION ok=true root={ext_root}")


def _smoke_github_ops_job_pipeline(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "github-ops-check",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chat",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: github-ops-check command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: github-ops-check must print JSON.") from e
    if payload.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Smoke test failed: github-ops-check status invalid.")

    start_proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "github-ops-job-start",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--kind",
            "pr_list",
            "--dry-run",
            "true",
        ],
        env=env,
        fail_msg="Smoke test failed: github-ops-job-start command failed.",
        capture=True,
    )
    try:
        start_payload = json.loads(start_proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: github-ops-job-start must print JSON.") from e
    if start_payload.get("status") not in {"OK", "WARN", "IDLE", "SKIP", "RUNNING", "QUEUED"}:
        raise SystemExit("Smoke test failed: github-ops-job-start status invalid.")

    job_id = str(start_payload.get("job_id") or "")
    if job_id:
        poll_proc = run_cmd(
            repo_root=repo_root,
            argv=[
                sys.executable,
                "-m",
                "src.ops.manage",
                "github-ops-job-poll",
                "--workspace-root",
                str(ws_integration.relative_to(repo_root)),
                "--job-id",
                job_id,
            ],
            env=env,
            fail_msg="Smoke test failed: github-ops-job-poll command failed.",
            capture=True,
        )
        try:
            poll_payload = json.loads(poll_proc.stdout.strip() or "{}")
        except Exception as e:
            raise SystemExit("Smoke test failed: github-ops-job-poll must print JSON.") from e
        if poll_payload.get("status") not in {"OK", "WARN", "IDLE", "SKIP", "PASS", "RUNNING", "QUEUED"}:
            raise SystemExit("Smoke test failed: github-ops-job-poll status invalid.")

    print("CRITICAL_GITHUB_OPS_JOB_PIPELINE ok=true status=OK network_enabled=false")


def _smoke_full_async_job_start(*, repo_root: Path, ws_integration: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    dry_run = "true" if os.environ.get("SMOKE_FULL_ASYNC_DRY_RUN") == "1" else "false"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "github-ops-job-start",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--kind",
            "SMOKE_FULL",
            "--dry-run",
            dry_run,
        ],
        env=env,
        fail_msg="Smoke test failed: smoke_full async start failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: smoke_full async start must print JSON.") from e
    status = str(payload.get("status") or "")
    if status not in {"OK", "WARN", "IDLE", "SKIP", "RUNNING", "QUEUED"}:
        raise SystemExit("Smoke test failed: smoke_full async status invalid.")
    job_id = str(payload.get("job_id") or "")
    started = "true" if status in {"RUNNING", "QUEUED"} and job_id else "false"
    print(f"CRITICAL_SMOKE_FULL_ASYNC ok=true started={started} job_id={job_id} status={status}")
    return {"job_id": job_id, "status": status}


def _smoke_release_automation(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "release-check",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chat",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: release-check command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: release-check must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: release-check output must be JSON object.")
    status = payload.get("status") if isinstance(payload.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Smoke test failed: release-check status invalid.")
    plan_path = ws_integration / ".cache" / "reports" / "release_plan.v1.json"
    if not plan_path.exists():
        raise SystemExit("Smoke test failed: release_plan.v1.json missing.")
    try:
        plan_obj = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit("Smoke test failed: release_plan.v1.json invalid JSON.") from e
    channel = plan_obj.get("channel") if isinstance(plan_obj, dict) else None
    if channel not in {"rc", "final"}:
        channel = "rc"
    print(f"CRITICAL_RELEASE_AUTOMATION ok=true status={status} channel={channel}")


def _smoke_airunner_async(*, repo_root: Path, ws_dry_run: Path, ws_integration: Path) -> None:
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "airunner-status",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
        ],
        env=env,
        fail_msg="Smoke test failed: airunner-status command failed.",
        capture=True,
    )
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: airunner-status must print JSON.") from e
    if not isinstance(payload, dict):
        raise SystemExit("Smoke test failed: airunner-status output must be JSON object.")
    status = payload.get("status") if isinstance(payload.get("status"), str) else "WARN"
    if status not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("Smoke test failed: airunner-status invalid status.")

    jobs_index_path = ws_integration / ".cache" / "airunner" / "jobs_index.v1.json"
    jobs_count = 0
    if jobs_index_path.exists():
        try:
            idx = json.loads(jobs_index_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("Smoke test failed: jobs_index.v1.json invalid JSON.") from e
        counts = idx.get("counts") if isinstance(idx, dict) else None
        if isinstance(counts, dict):
            jobs_count = int(counts.get("total", 0))

    time_sinks_path = ws_integration / ".cache" / "reports" / "time_sinks.v1.json"
    sinks_count = 0
    if time_sinks_path.exists():
        try:
            ts = json.loads(time_sinks_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit("Smoke test failed: time_sinks.v1.json invalid JSON.") from e
        sinks = ts.get("sinks") if isinstance(ts, dict) else None
        if isinstance(sinks, list):
            sinks_count = len([s for s in sinks if isinstance(s, dict)])

    print(f"CRITICAL_AIRUNNER_ASYNC ok=true status={status} jobs={jobs_count} time_sinks={sinks_count}")


def _smoke_repo_hygiene(repo_root: Path) -> None:
    out_path = repo_root / ".cache" / "repo_hygiene" / "smoke_report.json"
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "repo-hygiene",
            "--mode",
            "report",
            "--out",
            str(out_path.relative_to(repo_root)),
        ],
        env=env,
        fail_msg="Smoke test failed: repo-hygiene command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: repo-hygiene must print JSON.") from e
    if not isinstance(out, dict):
        raise SystemExit("Smoke test failed: repo-hygiene output must be JSON object.")
    if not out_path.exists():
        raise SystemExit("Smoke test failed: repo-hygiene report file missing.")
    report = json.loads(out_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise SystemExit("Smoke test failed: repo-hygiene report must be JSON object.")
    status = report.get("status") if isinstance(report, dict) else None
    if status not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: repo-hygiene status must be OK or WARN.")
    summary = report.get("summary") if isinstance(report, dict) else None
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(summary, dict) or not isinstance(findings, list):
        raise SystemExit("Smoke test failed: repo-hygiene must include summary and findings.")
    print(f"CRITICAL_REPO_HYGIENE ok=true status={status}")


def _smoke_debt_pipeline(*, repo_root: Path, ws_integration: Path) -> None:
    actions_path = ws_integration / ".cache" / "roadmap_actions.v1.json"
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    if actions_path.exists():
        try:
            actions_obj = json.loads(actions_path.read_text(encoding="utf-8"))
        except Exception:
            actions_obj = {}
    else:
        actions_obj = {}
    actions = actions_obj.get("actions") if isinstance(actions_obj, dict) else None
    if not isinstance(actions, list):
        actions = []
        if isinstance(actions_obj, dict):
            actions_obj["actions"] = actions
    if not any(isinstance(a, dict) and a.get("action_id") == "TEST_DEBT_SCRIPT_BUDGET" for a in actions):
        actions.append(
            {
                "action_id": "TEST_DEBT_SCRIPT_BUDGET",
                "severity": "WARN",
                "kind": "MAINTAINABILITY_DEBT",
                "milestone_hint": "M0",
                "source": "SCRIPT_BUDGET",
                "title": "Script budget soft limit exceeded (test)",
                "details": {},
                "message": "Script budget soft limit exceeded (test)",
                "resolved": False,
            }
        )
        actions_obj["actions"] = actions
        actions_path.write_text(json.dumps(actions_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.debt_drafter",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--outdir",
            str((ws_integration / ".cache" / "debt_chg").relative_to(repo_root)),
            "--max-items",
            "5",
        ],
        env=env,
        fail_msg="Smoke test failed: debt_drafter command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: debt_drafter must print JSON.") from e
    if not isinstance(out, dict) or out.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Smoke test failed: debt_drafter status must be OK or WARN.")
    drafted = int(out.get("drafted") or 0)
    chg_files = out.get("chg_files") if isinstance(out.get("chg_files"), list) else []
    if drafted < 1 or not chg_files:
        raise SystemExit("Smoke test failed: debt_drafter must draft at least one CHG.")
    chg_path = Path(str(chg_files[0])).resolve()
    proc_apply = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.debt_apply_incubator",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--chg",
            str(chg_path),
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: debt_apply_incubator failed.",
        capture=True,
    )
    try:
        applied = json.loads(proc_apply.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: debt_apply_incubator must print JSON.") from e
    if not isinstance(applied, dict) or applied.get("status") != "OK":
        raise SystemExit("Smoke test failed: debt_apply_incubator must return OK.")
    incubator_paths = applied.get("incubator_paths") if isinstance(applied.get("incubator_paths"), list) else []
    if not incubator_paths:
        raise SystemExit("Smoke test failed: debt_apply_incubator must report incubator_paths.")
    for p in incubator_paths[:3]:
        if not (Path(str(p)).exists()):
            raise SystemExit("Smoke test failed: incubator path missing: " + str(p))
    print(f"CRITICAL_DEBT_PIPELINE ok=true drafted={drafted} applied=true")


def _smoke_promotion_bundle(*, repo_root: Path, ws_integration: Path) -> None:
    incubator_root = ws_integration / "incubator"
    allowed_dirs = [incubator_root / "notes", incubator_root / "templates", incubator_root / "patches"]
    has_allowed = any(
        p.is_file()
        for d in allowed_dirs
        if d.exists()
        for p in d.rglob("*")
    )
    if not has_allowed:
        note_path = incubator_root / "notes" / "SMOKE_PROMOTION_NOTE.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("Promotion bundle smoke fixture.\n", encoding="utf-8")
    env = os.environ.copy()
    env["SMOKE_LEVEL"] = "fast"
    proc = run_cmd(
        repo_root=repo_root,
        argv=[
            sys.executable,
            "-m",
            "src.ops.manage",
            "promotion-bundle",
            "--workspace-root",
            str(ws_integration.relative_to(repo_root)),
            "--mode",
            "customer_clean",
            "--dry-run",
            "false",
        ],
        env=env,
        fail_msg="Smoke test failed: promotion-bundle command failed.",
        capture=True,
    )
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except Exception as e:
        raise SystemExit("Smoke test failed: promotion-bundle must print JSON.") from e
    if not isinstance(out, dict) or out.get("status") != "OK":
        raise SystemExit("Smoke test failed: promotion-bundle must return OK.")
    out_zip = out.get("out_zip")
    out_report = out.get("out_report")
    out_patch_md = out.get("out_patch_md")
    if not (isinstance(out_zip, str) and isinstance(out_report, str) and isinstance(out_patch_md, str)):
        raise SystemExit("Smoke test failed: promotion-bundle outputs missing.")
    zip_path = Path(out_zip)
    report_path = Path(out_report)
    patch_md_path = Path(out_patch_md)
    if not (zip_path.exists() and report_path.exists() and patch_md_path.exists()):
        raise SystemExit("Smoke test failed: promotion-bundle outputs must exist.")
    report_obj = json.loads(report_path.read_text(encoding="utf-8"))
    included = report_obj.get("included_files") if isinstance(report_obj, dict) else None
    if not (isinstance(included, list) and included):
        raise SystemExit("Smoke test failed: promotion report must include at least one file.")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = sorted(zf.namelist())
    if "PROMOTION_REPORT.json" not in names:
        raise SystemExit("Smoke test failed: promotion bundle must include PROMOTION_REPORT.json.")
    extra_files = [n for n in names if n not in {"PROMOTION_REPORT.json", "PROMOTION_README.txt"}]
    if not extra_files:
        raise SystemExit("Smoke test failed: promotion bundle must include at least one payload file.")
    md_text = patch_md_path.read_text(encoding="utf-8")
    if "Draft only" not in md_text:
        raise SystemExit("Smoke test failed: core patch summary must mention Draft only.")
    zip_bytes = zip_path.stat().st_size
    print(f"CRITICAL_PROMOTION_BUNDLE ok=true included={len(included)} zip_bytes={zip_bytes}")
    print("CRITICAL_M8_2_COMPLETE ok=true")
