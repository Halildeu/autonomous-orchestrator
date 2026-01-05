from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    # src/quality/quality_gate.py -> repo root
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class QualityPolicy:
    enabled: bool
    iso_gate_level: str
    required_iso_files: list[str]
    required_chat_sections: list[str]
    no_unsubstantiated_claims: bool
    evidence_required_for_pass_claims: bool
    policy_used: str


def _load_policy(core_root: Path) -> tuple[QualityPolicy, list[str]]:
    warnings: list[str] = []
    policy_path = core_root / "policies" / "policy_quality.v1.json"
    policy_used = "policies/policy_quality.v1.json"

    defaults = QualityPolicy(
        enabled=True,
        iso_gate_level="warn",
        required_iso_files=["context.v1.md", "stakeholders.v1.md", "scope.v1.md", "criteria.v1.md"],
        required_chat_sections=["PREVIEW", "RESULT", "EVIDENCE", "ACTIONS", "NEXT"],
        no_unsubstantiated_claims=True,
        evidence_required_for_pass_claims=True,
        policy_used=policy_used,
    )

    if not policy_path.exists():
        warnings.append("POLICY_MISSING:" + policy_used)
        return (defaults, warnings)

    try:
        obj = _load_json(policy_path)
    except Exception:
        warnings.append("POLICY_INVALID_JSON:" + policy_used)
        return (defaults, warnings)

    if not isinstance(obj, dict):
        warnings.append("POLICY_INVALID_SHAPE:" + policy_used)
        return (defaults, warnings)

    enabled = bool(obj.get("enabled", defaults.enabled))
    iso_gate_level = obj.get("iso_gate_level", defaults.iso_gate_level)
    if iso_gate_level not in {"warn", "block"}:
        warnings.append("POLICY_INVALID_ISO_GATE_LEVEL")
        iso_gate_level = defaults.iso_gate_level

    iso_files_raw = obj.get("required_iso_files", defaults.required_iso_files)
    required_iso_files = (
        [str(x) for x in iso_files_raw if isinstance(x, str) and x.strip()] if isinstance(iso_files_raw, list) else []
    )
    if not required_iso_files:
        warnings.append("POLICY_EMPTY_REQUIRED_ISO_FILES")
        required_iso_files = defaults.required_iso_files

    chat_raw = obj.get("required_chat_sections", defaults.required_chat_sections)
    required_chat_sections = (
        [str(x) for x in chat_raw if isinstance(x, str) and x.strip()] if isinstance(chat_raw, list) else []
    )
    if not required_chat_sections:
        warnings.append("POLICY_EMPTY_REQUIRED_CHAT_SECTIONS")
        required_chat_sections = defaults.required_chat_sections

    no_unsubstantiated_claims = bool(obj.get("no_unsubstantiated_claims", defaults.no_unsubstantiated_claims))
    evidence_required_for_pass_claims = bool(
        obj.get("evidence_required_for_pass_claims", defaults.evidence_required_for_pass_claims)
    )

    return (
        QualityPolicy(
            enabled=enabled,
            iso_gate_level=str(iso_gate_level),
            required_iso_files=required_iso_files,
            required_chat_sections=required_chat_sections,
            no_unsubstantiated_claims=no_unsubstantiated_claims,
            evidence_required_for_pass_claims=evidence_required_for_pass_claims,
            policy_used=policy_used,
        ),
        warnings,
    )


def _iso_missing(workspace_root: Path, required_files: list[str]) -> list[str]:
    base = workspace_root / "tenant" / "TENANT-DEFAULT"
    missing: list[str] = []
    for fname in required_files:
        rel = f"tenant/TENANT-DEFAULT/{fname}"
        if not (base / fname).exists():
            missing.append(rel)
    return missing


def _load_formats_index(workspace_root: Path) -> tuple[dict[str, Any] | None, str | None]:
    idx_path = workspace_root / ".cache" / "index" / "formats.v1.json"
    if not idx_path.exists():
        return (None, "FORMATS_INDEX_MISSING")
    try:
        obj = _load_json(idx_path)
    except Exception:
        return (None, "FORMATS_INDEX_INVALID_JSON")
    if not isinstance(obj, dict):
        return (None, "FORMATS_INDEX_INVALID_SHAPE")
    return (obj, None)


def _formats_index_has_id(index_obj: dict[str, Any], fmt_id: str) -> bool:
    formats = index_obj.get("formats")
    if not isinstance(formats, list):
        return False
    for item in formats:
        if isinstance(item, dict) and item.get("id") == fmt_id:
            return True
    return False


def _load_format_contract_by_id(*, core_root: Path, workspace_root: Path, fmt_id: str) -> tuple[dict[str, Any] | None, str]:
    ws_dir = workspace_root / "formats"
    if ws_dir.exists():
        for p in sorted(ws_dir.glob("*.v1.json"), key=lambda x: x.as_posix()):
            if not p.is_file():
                continue
            try:
                obj = _load_json(p)
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("id") == fmt_id:
                return (obj, "workspace")

    core_path = core_root / "formats" / "format-autopilot-chat.v1.json"
    if core_path.exists():
        try:
            obj = _load_json(core_path)
            if isinstance(obj, dict) and obj.get("id") == fmt_id:
                return (obj, "core")
        except Exception:
            pass
    return (None, "missing")


def _missing_required_sections(contract_obj: dict[str, Any], required_sections: list[str]) -> list[str]:
    sections = contract_obj.get("sections")
    present_required: set[str] = set()
    if isinstance(sections, list):
        for s in sections:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if not isinstance(sid, str):
                continue
            if s.get("required") is True:
                present_required.add(sid)

    missing: list[str] = []
    for sid in required_sections:
        if sid not in present_required:
            missing.append(sid)
    return missing


def evaluate_quality_gate(*, workspace_root: Path, core_root: Path | None = None) -> dict[str, Any]:
    core_root = core_root or _repo_root()
    policy, policy_warnings = _load_policy(core_root)

    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    warnings: list[str] = list(policy_warnings)

    if not policy.enabled:
        return {
            "status": "OK",
            "policy_used": policy.policy_used,
            "checks": [],
            "missing": [],
            "warnings": ["POLICY_DISABLED"],
        }

    # ISO presence check
    iso_missing_paths = _iso_missing(workspace_root, policy.required_iso_files)
    if iso_missing_paths:
        missing.extend(iso_missing_paths)
        iso_status = "FAIL" if policy.iso_gate_level == "block" else "WARN"
    else:
        iso_status = "OK"
    checks.append(
        {
            "id": "ISO_CORE",
            "status": iso_status,
            "gate_level": policy.iso_gate_level,
            "missing": iso_missing_paths,
        }
    )

    # Formats index check
    idx_obj, idx_err = _load_formats_index(workspace_root)
    if idx_obj is None:
        fmt_status = "WARN"
        if idx_err:
            warnings.append(idx_err)
        checks.append({"id": "FORMATS_INDEX", "status": fmt_status})
    else:
        checks.append({"id": "FORMATS_INDEX", "status": "OK"})

    # Autopilot chat format presence + contract sections
    autopilot_in_index = bool(idx_obj) and _formats_index_has_id(idx_obj, "FORMAT-AUTOPILOT-CHAT")
    if idx_obj is not None and not autopilot_in_index:
        warnings.append("FORMAT_ID_MISSING_IN_INDEX:FORMAT-AUTOPILOT-CHAT")

    contract_obj, contract_source = _load_format_contract_by_id(
        core_root=core_root,
        workspace_root=workspace_root,
        fmt_id="FORMAT-AUTOPILOT-CHAT",
    )
    if contract_obj is None:
        warnings.append("FORMAT_CONTRACT_MISSING:FORMAT-AUTOPILOT-CHAT")
        checks.append(
            {
                "id": "AUTOPILOT_CHAT_FORMAT",
                "status": "WARN",
                "format_id": "FORMAT-AUTOPILOT-CHAT",
                "source": contract_source,
            }
        )
    else:
        missing_sections = _missing_required_sections(contract_obj, policy.required_chat_sections)
        if missing_sections:
            missing.extend(["FORMAT_SECTION_MISSING:" + s for s in missing_sections])
            checks.append(
                {
                    "id": "AUTOPILOT_CHAT_FORMAT",
                    "status": "FAIL",
                    "format_id": "FORMAT-AUTOPILOT-CHAT",
                    "source": contract_source,
                    "missing_sections": missing_sections,
                }
            )
        else:
            checks.append(
                {
                    "id": "AUTOPILOT_CHAT_FORMAT",
                    "status": "OK",
                    "format_id": "FORMAT-AUTOPILOT-CHAT",
                    "source": contract_source,
                }
            )

    status = "OK"
    if any(isinstance(c, dict) and c.get("status") == "FAIL" for c in checks):
        status = "FAIL"
    elif any(isinstance(c, dict) and c.get("status") == "WARN" for c in checks) or missing or warnings:
        status = "WARN"

    return {
        "status": status,
        "policy_used": policy.policy_used,
        "checks": checks,
        "missing": sorted(set(str(x) for x in missing if isinstance(x, str) and x)),
        "warnings": sorted(set(str(x) for x in warnings if isinstance(x, str) and x)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.quality.quality_gate", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    core_root = _repo_root()
    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(_dump_json({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID", "message": str(workspace_root)}).strip())
        return 2

    out_path = Path(str(args.out)).resolve()
    if not _is_within_root(out_path, workspace_root):
        print(
            _dump_json(
                {
                    "status": "FAIL",
                    "error_code": "OUTSIDE_WORKSPACE_ROOT",
                    "message": "out path must be within workspace-root",
                    "out": str(out_path),
                }
            ).strip()
        )
        return 2

    report = evaluate_quality_gate(workspace_root=workspace_root, core_root=core_root)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_dump_json(report), encoding="utf-8")
    except Exception as e:
        print(
            _dump_json({"status": "FAIL", "error_code": "WRITE_FAILED", "message": str(e)[:300], "out": str(out_path)}).strip()
        )
        return 2

    # Print compact JSON for ops visibility (no secrets).
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report.get("status") == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
