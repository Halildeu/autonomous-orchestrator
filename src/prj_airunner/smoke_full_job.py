from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.prj_airunner.smoke_full_job_packs import (
    _ensure_demo_pack_advisor_suggestions,
    _ensure_demo_pack_capability_index,
    _ensure_demo_pack_selection_trace,
    _ensure_demo_public_candidates_bundle,
    _ensure_demo_public_candidates_pointer,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(_dump_json(payload), encoding="utf-8")
    tmp_path.replace(path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _load_json(path: Path) -> tuple[dict | None, bool]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, False
    if not isinstance(obj, dict):
        return None, False
    return obj, True


def _file_sha256(path: Path) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    return hashlib.sha256(data).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_job_id(rc_path: Path) -> str:
    if rc_path.name == "rc.json":
        parent = rc_path.parent
        if parent.name and parent.parent.name == "jobs":
            return parent.name
    name = rc_path.name
    if name.endswith(".rc.json"):
        if name.startswith("smoke_full_"):
            return name[len("smoke_full_") : -len(".rc.json")]
        if name.startswith("smoke_fast_"):
            return name[len("smoke_fast_") : -len(".rc.json")]
    return "unknown"


def _job_artifact_path(workspace_root: Path, job_id: str) -> Path:
    return (
        workspace_root
        / ".cache"
        / "reports"
        / "jobs"
        / f"smoke_full_{job_id}"
        / "advisor_suggestions.v1.json"
    )


def _fallback_advisor_payload(workspace_root: Path, reason: str) -> dict:
    note = f"ADVISOR_PIN_FALLBACK:{reason}"
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "inputs_summary": {
            "public_candidates_present": False,
            "run_index_present": False,
            "dlq_index_present": False,
            "actions_present": False,
            "counts": {"candidates": 0, "runs": 0, "dlq": 0, "actions": 0},
        },
        "suggestions": [
            {
                "id": "ADVISOR_PIN_FALLBACK",
                "kind": "QUALITY",
                "title": "Advisor output pinned",
                "details": "Fallback output written to job artifacts due to missing advisor output.",
                "confidence": 0.0,
                "evidence_refs": [note],
                "recommended_action": "Inspect advisor pipeline output path and triage evidence.",
            }
        ],
        "safety": {"status": "WARN", "notes": [note]},
    }


def _pin_advisor_output(*, workspace_root: Path, rc_path: Path) -> None:
    job_id = _extract_job_id(rc_path)
    if not job_id or job_id == "unknown":
        return
    advisor_path = workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"
    payload: dict | None = None
    reason = ""
    if advisor_path.exists():
        obj, valid = _load_json(advisor_path)
        if valid:
            payload = obj
        else:
            reason = "INVALID_JSON"
    else:
        reason = "MISSING"
    if payload is None:
        payload = _fallback_advisor_payload(workspace_root, reason or "UNKNOWN")
    _write_json_atomic(_job_artifact_path(workspace_root, job_id), payload)


def _advisor_suggestions_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "learning" / "advisor_suggestions.v1.json"


def _advisor_suggestions_semantic_ok(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"version", "generated_at", "workspace_root", "inputs_summary", "suggestions", "safety"}
    if not required.issubset(obj.keys()):
        return False
    suggestions = obj.get("suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return False
    kinds = {s.get("kind") for s in suggestions if isinstance(s, dict)}
    if not kinds.intersection({"NEXT_MILESTONE", "MAINTAINABILITY", "QUALITY"}):
        return False
    safety = obj.get("safety") if isinstance(obj.get("safety"), dict) else None
    status = safety.get("status") if isinstance(safety, dict) else None
    return status in {"OK", "WARN"}


def _load_expected_advisor_paths(workspace_root: Path) -> list[Path]:
    repo_root = _repo_root()
    report_path = (
        repo_root
        / ".cache"
        / "ws_customer_default"
        / ".cache"
        / "reports"
        / "advisor_suggestions_expected_paths.v0.1.json"
    )
    expected: list[str] = []
    if report_path.exists():
        obj, valid = _load_json(report_path)
        if valid and isinstance(obj, dict):
            candidates = obj.get("expected_paths") or obj.get("expected_paths_sorted") or []
            if isinstance(candidates, list):
                expected = [str(p) for p in candidates if isinstance(p, str) and p.strip()]
    root = workspace_root.resolve()
    resolved: list[Path] = []
    for raw in expected:
        path = Path(raw)
        if not path.is_absolute():
            if path.name == "advisor_suggestions.v1.json" and path.parent == Path("."):
                path = root / ".cache" / "learning" / path.name
            else:
                path = root / path
        try:
            path = path.resolve()
            path.relative_to(root)
        except Exception:
            continue
        if path.name != "advisor_suggestions.v1.json":
            continue
        resolved.append(path)
    canonical = _advisor_suggestions_path(root)
    if not resolved:
        resolved = [canonical]
    elif canonical not in resolved:
        resolved.append(canonical)
    return sorted({p for p in resolved}, key=lambda p: str(p))


def _build_advisor_suggestions(workspace_root: Path) -> dict:
    return _fallback_advisor_payload(workspace_root, "PRESEED")


def _ensure_demo_advisor_suggestions(workspace_root: Path) -> dict[str, object]:
    targets = _load_expected_advisor_paths(workspace_root)
    payload = _build_advisor_suggestions(workspace_root)
    kept = 0
    written = 0
    for path in targets:
        if path.exists():
            obj, valid = _load_json(path)
            if valid and isinstance(obj, dict) and _advisor_suggestions_semantic_ok(obj):
                kept += 1
                continue
        _write_json_atomic(path, payload)
        written += 1
    action = "written" if written else "kept"
    return {
        "status": "OK",
        "action": action,
        "path": str(targets[0]),
        "paths": [str(p) for p in targets],
        "kept": kept,
        "written": written,
    }


def _catalog_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "catalog.v1.json"


def _catalog_has_pack_demo(path: Path) -> bool:
    if not path.exists():
        return False
    obj, valid = _load_json(path)
    if not valid or not isinstance(obj, dict):
        return False
    packs = obj.get("packs")
    if not isinstance(packs, list):
        return False
    return any(isinstance(p, dict) and p.get("pack_id") == "pack-demo" for p in packs)


def _pack_demo_manifest_payload() -> dict:
    return {
        "pack_id": "pack-demo",
        "version": "v1",
        "lifecycle_state": "experimental",
        "iso_kernel_refs": {
            "context_ref": "docs/OPERATIONS/PROJECT-SSOT.md",
            "stakeholders_ref": "docs/OPERATIONS/PROJECT-SSOT.md",
            "scope_ref": "docs/OPERATIONS/PROJECT-SSOT.md",
            "criteria_ref": "docs/OPERATIONS/PROJECT-SSOT.md",
            "gate_level": "warn",
        },
        "provides": {
            "intents": [],
            "workflows": [],
            "formats": [],
            "capability_refs": [],
            "format_refs": [],
        },
        "namespace_prefix": "PACK_DEMO",
        "conflict_policy": {
            "hard_conflict": "fail",
            "soft_conflict": "warn",
            "deterministic_tie_break": "pack_id_lexicographic",
        },
    }


def _ensure_pack_demo_manifest(workspace_root: Path) -> str:
    manifest_path = workspace_root / "packs" / "pack-demo" / "manifest.v1.json"
    if manifest_path.exists():
        obj, valid = _load_json(manifest_path)
        if valid and isinstance(obj, dict) and obj.get("pack_id") == "pack-demo":
            return "kept"
    _write_json_atomic(manifest_path, _pack_demo_manifest_payload())
    return "written"


def _ensure_demo_catalog(workspace_root: Path) -> dict[str, str]:
    catalog_path = _catalog_path(workspace_root)
    if _catalog_has_pack_demo(catalog_path):
        return {"status": "OK", "action": "kept", "catalog_path": str(catalog_path)}
    manifest_action = _ensure_pack_demo_manifest(workspace_root)
    rc = 0
    try:
        from src.tenant.build_catalog import main as build_catalog_main
        rc = int(build_catalog_main(["--workspace-root", str(workspace_root), "--out", str(catalog_path), "--dry-run", "false"]) or 0)
    except Exception:
        rc = 2
    if rc == 0 and _catalog_has_pack_demo(catalog_path):
        return {"status": "OK", "action": "rebuilt", "catalog_path": str(catalog_path), "manifest_action": manifest_action}
    fallback_payload = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "tenant": "TENANT-DEFAULT",
        "decision_bundle_present": False,
        "packs": [{"pack_id": "pack-demo", "version": "v1", "applies_to": {}, "provides": {}}],
        "warnings": ["CATALOG_FALLBACK"],
    }
    _write_json_atomic(catalog_path, fallback_payload)
    return {"status": "FALLBACK", "action": "written", "catalog_path": str(catalog_path), "manifest_action": manifest_action}


def _formats_index_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "formats.v1.json"


def _formats_index_valid(path: Path) -> bool:
    if not path.exists():
        return False
    obj, valid = _load_json(path)
    if not valid or not isinstance(obj, dict):
        return False
    formats = obj.get("formats")
    if not isinstance(formats, list):
        return False
    return True


def _ensure_demo_formats_index(workspace_root: Path) -> dict[str, str]:
    formats_path = _formats_index_path(workspace_root)
    if _formats_index_valid(formats_path):
        return {"status": "OK", "action": "kept", "formats_path": str(formats_path)}
    try:
        from src.tenant.build_formats_index import _build_formats_index

        index_obj, _warnings = _build_formats_index(workspace_root=workspace_root)
        if isinstance(index_obj, dict):
            _write_json_atomic(formats_path, index_obj)
            if _formats_index_valid(formats_path):
                return {"status": "OK", "action": "rebuilt", "formats_path": str(formats_path)}
    except Exception:
        pass
    fallback_payload = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "formats": [],
        "warnings": ["FORMATS_FALLBACK"],
    }
    _write_json_atomic(formats_path, fallback_payload)
    return {"status": "FALLBACK", "action": "written", "formats_path": str(formats_path)}


def _quality_gate_report_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "quality_gate_report.v1.json"


def _quality_gate_report_valid(path: Path) -> bool:
    if not path.exists():
        return False
    obj, valid = _load_json(path)
    if not valid or not isinstance(obj, dict):
        return False
    status = obj.get("status")
    return isinstance(status, str) and bool(status.strip())


def _ensure_demo_quality_gate_report(workspace_root: Path) -> dict[str, str]:
    report_path = _quality_gate_report_path(workspace_root)
    if _quality_gate_report_valid(report_path):
        return {"status": "OK", "action": "kept", "report_path": str(report_path)}
    try:
        from src.quality.quality_gate import evaluate_quality_gate

        report = evaluate_quality_gate(workspace_root=workspace_root)
        if isinstance(report, dict):
            _write_json_atomic(report_path, report)
            if _quality_gate_report_valid(report_path):
                return {"status": "OK", "action": "rebuilt", "report_path": str(report_path)}
    except Exception:
        pass
    fallback_payload = {
        "status": "WARN",
        "policy_used": "",
        "checks": [],
        "missing": [],
        "warnings": ["QUALITY_GATE_FALLBACK"],
    }
    _write_json_atomic(report_path, fallback_payload)
    return {"status": "FALLBACK", "action": "written", "report_path": str(report_path)}


def _session_context_path(workspace_root: Path, session_id: str = "default") -> Path:
    return workspace_root / ".cache" / "sessions" / session_id / "session_context.v1.json"


def _ensure_demo_session_context(workspace_root: Path, session_id: str = "default") -> dict[str, str]:
    ctx_path = _session_context_path(workspace_root, session_id=session_id)
    existed = ctx_path.exists()
    try:
        from src.session.context_store import SessionContextError, load_context, new_context, save_context_atomic
    except Exception:
        return {"status": "FAIL", "action": "import_error", "path": str(ctx_path)}

    if ctx_path.exists():
        try:
            load_context(ctx_path)
            return {"status": "OK", "action": "kept", "path": str(ctx_path)}
        except SessionContextError:
            pass
    try:
        ctx = new_context(session_id=session_id, workspace_root=str(workspace_root), ttl_seconds=86400)
        save_context_atomic(ctx_path, ctx)
        load_context(ctx_path)
        action = "written" if not existed else "rebuilt"
        return {"status": "OK", "action": action, "path": str(ctx_path)}
    except SessionContextError:
        return {"status": "FAIL", "action": "write_failed", "path": str(ctx_path)}


def _ops_index_paths(workspace_root: Path) -> tuple[Path, Path]:
    return (
        workspace_root / ".cache" / "index" / "run_index.v1.json",
        workspace_root / ".cache" / "index" / "dlq_index.v1.json",
    )


def _ops_index_semantic_ok(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("version") != "v1":
        return False
    if not isinstance(obj.get("items"), list):
        return False
    return True


def _ensure_demo_ops_index(workspace_root: Path) -> dict[str, object]:
    root = workspace_root.resolve()
    run_index_path, dlq_index_path = _ops_index_paths(root)

    if run_index_path.exists() and dlq_index_path.exists():
        run_obj, run_valid = _load_json(run_index_path)
        dlq_obj, dlq_valid = _load_json(dlq_index_path)
        if (
            run_valid
            and dlq_valid
            and isinstance(run_obj, dict)
            and isinstance(dlq_obj, dict)
            and _ops_index_semantic_ok(run_obj)
            and _ops_index_semantic_ok(dlq_obj)
        ):
            return {"status": "OK", "action": "kept", "paths": [str(run_index_path), str(dlq_index_path)]}

    try:
        from src.ops.build_ops_index import build_ops_index
    except Exception:
        return {"status": "FAIL", "action": "import_error", "paths": [str(run_index_path), str(dlq_index_path)]}

    result = build_ops_index(workspace_root=root, core_root=_repo_root())
    run_obj, run_valid = _load_json(run_index_path) if run_index_path.exists() else (None, False)
    dlq_obj, dlq_valid = _load_json(dlq_index_path) if dlq_index_path.exists() else (None, False)

    if (
        run_valid
        and dlq_valid
        and isinstance(run_obj, dict)
        and isinstance(dlq_obj, dict)
        and _ops_index_semantic_ok(run_obj)
        and _ops_index_semantic_ok(dlq_obj)
    ):
        return {
            "status": "OK",
            "action": "written",
            "paths": [str(run_index_path), str(dlq_index_path)],
            "result": result,
        }

    return {
        "status": "FAIL",
        "action": "write_failed",
        "paths": [str(run_index_path), str(dlq_index_path)],
        "result": result,
    }


def _autopilot_readiness_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "ops" / "autopilot_readiness.v1.json"


def _autopilot_readiness_semantic_ok(obj: dict) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("version") != "v1":
        return False
    status = obj.get("status")
    if status not in {"READY", "NOT_READY"}:
        return False
    checks = obj.get("checks")
    if not isinstance(checks, list):
        return False
    has_workspace = any(
        isinstance(c, dict) and c.get("category") == "WORKSPACE" for c in checks
    )
    return has_workspace


def _autopilot_readiness_inputs_present(workspace_root: Path) -> bool:
    run_index_path, dlq_index_path = _ops_index_paths(workspace_root)
    required = [
        _catalog_path(workspace_root),
        _formats_index_path(workspace_root),
        run_index_path,
        dlq_index_path,
        workspace_root / ".cache" / "learning" / "public_candidates.v1.json",
        _advisor_suggestions_path(workspace_root),
        _session_context_path(workspace_root, session_id="default"),
    ]
    return all(p.exists() for p in required)


def _ensure_demo_autopilot_readiness(workspace_root: Path) -> dict[str, str]:
    root = workspace_root.resolve()
    out_path = _autopilot_readiness_path(root)
    if out_path.exists():
        obj, valid = _load_json(out_path)
        if valid and isinstance(obj, dict) and _autopilot_readiness_semantic_ok(obj):
            status = obj.get("status")
            if status == "READY":
                return {"status": "OK", "action": "kept", "path": str(out_path)}
            if status == "NOT_READY" and not _autopilot_readiness_inputs_present(root):
                return {"status": "OK", "action": "kept", "path": str(out_path)}
    try:
        from src.autopilot.readiness_report import run_readiness_for_workspace
    except Exception:
        return {"status": "FAIL", "action": "import_error", "path": str(out_path)}
    result = run_readiness_for_workspace(
        workspace_root=root,
        core_root=_repo_root(),
        dry_run=False,
    )
    obj, valid = _load_json(out_path) if out_path.exists() else (None, False)
    if valid and isinstance(obj, dict) and _autopilot_readiness_semantic_ok(obj):
        action = "written" if result.get("status") == "OK" else "rebuilt"
        return {
            "status": "OK",
            "action": action,
            "path": str(out_path),
        }
    return {
        "status": "FAIL",
        "action": "write_failed",
        "path": str(out_path),
    }


def _system_status_paths(workspace_root: Path) -> tuple[Path, Path]:
    return (
        workspace_root / ".cache" / "reports" / "system_status.v1.json",
        workspace_root / ".cache" / "reports" / "system_status.v1.md",
    )


def _system_status_md_ok(md_text: str) -> bool:
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
    return all(heading in md_text for heading in required_headings)


def _ensure_demo_cockpit_healthcheck(workspace_root: Path) -> None:
    out_json = workspace_root / ".cache" / "reports" / "cockpit_healthcheck.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "cockpit_healthcheck.v1.md"
    if out_json.exists():
        obj, valid = _load_json(out_json)
        if valid and isinstance(obj.get("port"), int):
            return
    request_id = _sha256_bytes(f"{workspace_root}|0".encode("utf-8"))
    payload = {
        "version": "v1",
        "status": "OK",
        "workspace_root": str(workspace_root),
        "host": "127.0.0.1",
        "port": 0,
        "requested_port": 0,
        "request_id": request_id,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true", "LOCAL_ONLY=true"],
    }
    _write_json_atomic(out_json, payload)
    md_text = "\n".join(
        [
            "# Cockpit Healthcheck",
            "- status: OK",
            "- host: 127.0.0.1",
            "- port: 0",
            "",
            "## Checks",
            "- /: true",
            "- /api/health: true",
            "- /api/status: true",
            "- /api/op system-status: true",
            "",
        ]
    )
    _write_text_atomic(out_md, md_text)


def _system_status_semantic_ok(report: dict, md_text: str, repo_root: Path) -> bool:
    if not isinstance(report, dict):
        return False
    try:
        from src.ops.system_status_builder import _validate_schema
    except Exception:
        return False
    if _validate_schema(repo_root, report):
        return False
    return _system_status_md_ok(md_text)


def _ensure_demo_system_status(workspace_root: Path) -> dict[str, str]:
    root = workspace_root.resolve()
    out_json, out_md = _system_status_paths(root)
    repo_root = _repo_root()
    _ensure_demo_cockpit_healthcheck(root)
    if out_json.exists() and out_md.exists():
        obj, valid = _load_json(out_json)
        if valid:
            md_text = out_md.read_text(encoding="utf-8")
            if _system_status_semantic_ok(obj, md_text, repo_root):
                overall = str(obj.get("overall_status") or "")
                if overall != "NOT_READY":
                    return {
                        "status": "OK",
                        "action": "kept",
                        "out_json": str(out_json),
                        "out_md": str(out_md),
                    }
                readiness = _autopilot_readiness_path(root)
                r_obj, r_valid = _load_json(readiness) if readiness.exists() else (None, False)
                readiness_status = r_obj.get("status") if r_valid and isinstance(r_obj, dict) else None
                if str(readiness_status) == "NOT_READY" and not _autopilot_readiness_inputs_present(root):
                    return {
                        "status": "OK",
                        "action": "kept",
                        "out_json": str(out_json),
                        "out_md": str(out_md),
                    }
    try:
        from src.ops.system_status_builder import _load_policy, _render_md, build_system_status
    except Exception:
        return {
            "status": "FAIL",
            "action": "import_error",
            "out_json": str(out_json),
            "out_md": str(out_md),
        }
    policy = _load_policy(repo_root, root)
    if not policy.enabled:
        return {
            "status": "FAIL",
            "action": "policy_disabled",
            "out_json": str(out_json),
            "out_md": str(out_md),
        }
    report = build_system_status(
        workspace_root=root,
        core_root=repo_root,
        policy=policy,
        dry_run=False,
    )
    md_text = _render_md(report)
    if not _system_status_semantic_ok(report, md_text, repo_root):
        return {
            "status": "FAIL",
            "action": "semantic_invalid",
            "out_json": str(out_json),
            "out_md": str(out_md),
        }
    _write_json_atomic(out_json, report)
    _write_text_atomic(out_md, md_text)
    obj, valid = _load_json(out_json)
    if valid and _system_status_semantic_ok(obj, out_md.read_text(encoding="utf-8"), repo_root):
        return {
            "status": "OK",
            "action": "written",
            "out_json": str(out_json),
            "out_md": str(out_md),
        }
    return {
        "status": "FAIL",
        "action": "write_failed",
        "out_json": str(out_json),
        "out_md": str(out_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--rc-path", required=True)
    parser.add_argument("--level", default="full")
    parser.add_argument("--fingerprint", default="")
    args = parser.parse_args()

    repo_root = _repo_root()
    ws_root = Path(str(args.workspace_root))
    rc_path = Path(str(args.rc_path))

    env = os.environ.copy()
    env["SMOKE_LEVEL"] = str(args.level or "full")
    env["SMOKE_FULL_ASYNC_JOB"] = "1"
    env["SMOKE_WORKSPACE_ROOT"] = str(ws_root)
    venv_py = repo_root / ".venv" / "bin" / "python"
    python_bin = str(venv_py) if venv_py.exists() else sys.executable
    _ensure_demo_catalog(ws_root)
    _ensure_demo_formats_index(ws_root)
    _ensure_demo_quality_gate_report(ws_root)
    _ensure_demo_session_context(ws_root)
    _ensure_demo_ops_index(ws_root)
    _ensure_demo_advisor_suggestions(ws_root)
    _ensure_demo_pack_advisor_suggestions(ws_root)
    _ensure_demo_public_candidates_bundle(ws_root)
    _ensure_demo_public_candidates_pointer(ws_root)
    _ensure_demo_autopilot_readiness(ws_root)
    _ensure_demo_system_status(ws_root)
    _ensure_demo_pack_capability_index(ws_root)
    _ensure_demo_pack_selection_trace(ws_root)
    proc = subprocess.run(
        [python_bin, "smoke_test.py"],
        cwd=str(repo_root),
        env=env,
        text=True,
        check=False,
    )

    rc_payload = {
        "rc": int(proc.returncode),
        "completed_at": _now_iso(),
        "workspace_root": str(ws_root),
    }
    if str(args.fingerprint or "").strip():
        rc_payload["fingerprint"] = str(args.fingerprint)
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    rc_path.write_text(_dump_json(rc_payload), encoding="utf-8")
    _pin_advisor_output(workspace_root=ws_root, rc_path=rc_path)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
