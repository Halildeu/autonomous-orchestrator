from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_hex(s: str) -> str:
    return sha256(s.encode("utf-8")).hexdigest()


def _normalize_script_budget_report(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {"status": "FAIL", "hard_exceeded": 0, "soft_exceeded": 0}
    exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []
    exceeded_soft = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
    function_hard = report.get("function_hard") if isinstance(report.get("function_hard"), list) else []
    function_soft = report.get("function_soft") if isinstance(report.get("function_soft"), list) else []
    hard_exceeded = len(exceeded_hard) + len(function_hard)
    soft_exceeded = len(exceeded_soft) + len(function_soft)
    report["hard_exceeded"] = hard_exceeded
    report["soft_exceeded"] = soft_exceeded
    report.setdefault("soft_only", hard_exceeded == 0 and soft_exceeded > 0)
    return report


@dataclass(frozen=True)
class _CmdResult:
    returncode: int
    stdout: str
    stderr: str


def _run_cmd(core_root: Path, argv: list[str], *, env: dict[str, str]) -> _CmdResult:
    proc = subprocess.run(argv, cwd=core_root, text=True, capture_output=True, env=env)
    return _CmdResult(returncode=int(proc.returncode), stdout=(proc.stdout or ""), stderr=(proc.stderr or ""))


def _run_script_budget_checker(*, core_root: Path) -> tuple[str, dict[str, Any]]:
    report_path = (core_root / ".cache" / "script_budget" / "report.json").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(core_root / "ci" / "check_script_budget.py"), "--out", str(report_path)],
        cwd=core_root,
        text=True,
        capture_output=True,
    )
    try:
        obj = _load_json(report_path) if report_path.exists() else {}
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}

    status = obj.get("status")
    if status not in {"OK", "WARN", "FAIL"}:
        status = "FAIL" if proc.returncode != 0 else "WARN"
    obj.setdefault("status", status)
    obj = _normalize_script_budget_report(obj)
    try:
        report_path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    return (str(status), obj)


def _run_quality_gate_checker(*, core_root: Path, workspace_root: Path) -> tuple[str, dict[str, Any]]:
    try:
        from src.quality.quality_gate import evaluate_quality_gate
    except Exception as e:
        msg = str(e)[:300]
        report = {"status": "FAIL", "error_code": "QUALITY_GATE_IMPORT_FAILED", "message": msg}
        return ("FAIL", report)

    try:
        report = evaluate_quality_gate(workspace_root=workspace_root, core_root=core_root)
    except Exception as e:
        msg = str(e)[:300]
        report = {"status": "FAIL", "error_code": "QUALITY_GATE_EXCEPTION", "message": msg}

    if not isinstance(report, dict):
        report = {"status": "FAIL", "error_code": "QUALITY_GATE_INVALID_REPORT"}
    status = report.get("status")
    if status not in {"OK", "WARN", "FAIL"}:
        status = "FAIL"
    report.setdefault("status", status)
    return (str(status), report)


def _quality_gate_warn_action_from_report(report: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    if report.get("status") != "WARN":
        return None

    missing = report.get("missing") if isinstance(report.get("missing"), list) else []
    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    missing_s = sorted({str(x) for x in missing if isinstance(x, str) and x})
    warnings_s = sorted({str(x) for x in warnings if isinstance(x, str) and x})

    details = {"missing": missing_s[:10], "warnings": warnings_s[:10]}
    title = "Quality gate warnings"
    msg_parts: list[str] = []
    if details["missing"]:
        msg_parts.append("missing=" + ",".join(details["missing"][:5]))
    if details["warnings"]:
        msg_parts.append("warnings=" + ",".join(details["warnings"][:5]))
    msg = (title + (": " + " ".join(msg_parts) if msg_parts else ""))[:300]

    seed = "QUALITY_GATE|WARN|" + "|".join(details["missing"] + details["warnings"])
    action_id = _sha256_hex(seed)[:16]

    return {
        "action_id": action_id,
        "severity": "WARN",
        "kind": "QUALITY_GATE_WARN",
        "milestone_hint": "M6",
        "source": "QUALITY_GATE",
        "target_milestone": "M6",
        "title": title,
        "details": details,
        "recommendation": "Run M6 and ensure ISO core docs + formats index exist; keep output standards enforced.",
        "resolved": False,
        "message": msg,
    }


def _run_ops_index_builder(*, core_root: Path, workspace_root: Path) -> tuple[str, dict[str, Any]]:
    try:
        from src.ops.build_ops_index import build_ops_index

        report = build_ops_index(workspace_root=workspace_root, core_root=core_root)
    except Exception as e:
        return ("FAIL", {"status": "FAIL", "error_code": "OPS_INDEX_EXCEPTION", "message": str(e)[:300]})

    status = report.get("status")
    if status == "SKIPPED":
        return ("OK", report)
    if status not in {"OK", "WARN", "FAIL"}:
        status = "FAIL"
        report["status"] = "FAIL"
        report.setdefault("error_code", "OPS_INDEX_INVALID_STATUS")
    return (str(status), report)


def _ops_index_action_from_report(report: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    status = report.get("status")
    if status != "WARN":
        return None
    run_count = report.get("run_count")
    dlq_count = report.get("dlq_count")
    parse_errors = report.get("parse_errors")
    seed = f"OPS_INDEX|{status}"
    action_id = _sha256_hex(seed)[:16]
    msg = f"Ops index WARN: runs={run_count} dlq={dlq_count} parse_errors={parse_errors}"
    return {
        "action_id": action_id,
        "severity": "WARN",
        "kind": "OPS_INDEX_WARN",
        "milestone_hint": "M6.6",
        "source": "OPS_INDEX",
        "target_milestone": "M6.6",
        "title": "Ops index produced with warnings",
        "details": {
            "run_count": run_count,
            "dlq_count": dlq_count,
            "parse_errors": parse_errors,
        },
        "recommendation": "Keep scans bounded; review parse errors and index sources.",
        "resolved": False,
        "message": msg[:300],
    }


def _pack_manifest_sha_map(core_root: Path, workspace_root: Path) -> dict[str, str]:
    manifests: list[Path] = []
    core_dir = core_root / "packs"
    if core_dir.exists():
        manifests.extend(sorted(core_dir.rglob("pack.manifest.v1.json")))
    ws_dir = workspace_root / "packs"
    if ws_dir.exists():
        manifests.extend(sorted(ws_dir.rglob("pack.manifest.v1.json")))
    sha_map: dict[str, str] = {}
    for path in manifests:
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except Exception:
            continue
        try:
            obj = _load_json(path)
        except Exception:
            continue
        pack_id = obj.get("pack_id") if isinstance(obj, dict) else None
        if not isinstance(pack_id, str):
            continue
        sha_map[pack_id] = sha256(data).hexdigest()
    return sha_map


def _pack_list_sha(sha_map: dict[str, str]) -> str | None:
    if not sha_map:
        return None
    payload = "\n".join(f"{pid}:{sha_map.get(pid, '')}" for pid in sorted(sha_map)).encode("utf-8")
    return sha256(payload).hexdigest()


def _pack_validation_report_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "pack_validation_report.json"


def _run_pack_validation(
    *,
    core_root: Path,
    workspace_root: Path,
    logs: list[str],
) -> tuple[dict[str, Any] | None, str, int]:
    report_path = _pack_validation_report_path(workspace_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ORCH_ROADMAP_RUNNER"] = "1"
    cmd = [
        sys.executable,
        "-m",
        "ci.validate_pack_manifest",
        "--workspace-root",
        str(workspace_root),
        "--out",
        str(report_path),
    ]
    res = _run_cmd(core_root, cmd, env=env)
    report_obj: dict[str, Any] | None = None
    if report_path.exists():
        try:
            report_obj = _load_json(report_path)
        except Exception as e:
            logs.append("PACK_VALIDATION_REPORT_INVALID " + str(e)[:200] + "\n")
    return (report_obj, str(report_path), res.returncode)


def _pack_conflict_action(
    *,
    kind: str,
    severity: str,
    report_path: str,
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    top = conflicts[:3] if isinstance(conflicts, list) else []
    details = []
    for c in top:
        if not isinstance(c, dict):
            continue
        label = c.get("kind") or c.get("intent") or c.get("capability_id") or c.get("format_id") or ""
        if isinstance(label, str) and label:
            details.append(label)
    detail_text = ", ".join(details)
    msg = f"Pack conflicts detected; see {report_path}."
    if detail_text:
        msg += " Top: " + detail_text
    return {
        "action_id": _sha256_hex(f"{kind}|{report_path}|{len(conflicts)}")[:16],
        "kind": kind,
        "severity": severity,
        "milestone_hint": "M9.2",
        "title": "Pack conflict detected",
        "message": msg,
        "resolved": False,
    }
