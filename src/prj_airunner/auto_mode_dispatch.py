from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _policy_defaults() -> dict[str, Any]:
    return {
        "version": "v1",
        "enabled": False,
        "mode": "mixed",
        "limits": {
            "max_ticks_per_run": 1,
            "max_actions_per_tick": 3,
            "max_jobs_start_per_tick": 1,
            "max_polls_per_tick": 2,
        },
        "dispatch": {
            "prefer_selected_autopilot": True,
            "prefer_suggested_extension": True,
            "fallback_mapping": {
                "GITHUB_OPS": "PRJ-GITHUB-OPS",
                "RELEASE": "PRJ-RELEASE-AUTOMATION",
                "JOB_STATUS": "PRJ-AIRUNNER",
                "MANUAL_REQUEST:doc-only": "PRJ-AIRUNNER",
            },
        },
        "network_gate": {
            "default_network_enabled": False,
            "require_extension_policy_enable": True,
        },
        "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
    }


def load_auto_mode_policy(*, workspace_root: Path) -> tuple[dict[str, Any], str, str, list[str]]:
    notes: list[str] = []
    policy = _policy_defaults()
    policy_source = "core"

    core_path = _repo_root() / "policies" / "policy_auto_mode.v1.json"
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_auto_mode.override.v1.json"

    for path, source_label in [(core_path, "core"), (override_path, "workspace_override")]:
        if not path.exists():
            continue
        try:
            obj = _load_json(path)
        except Exception:
            notes.append(f"auto_mode_policy_invalid:{source_label}")
            continue
        if isinstance(obj, dict):
            policy = _deep_merge(policy, obj)
            if source_label != "core":
                policy_source = "core+workspace_override"

    policy_hash = _hash_text(_canonical_json(policy))
    return policy, policy_source, policy_hash, notes


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(priority, 99)


def _severity_rank(severity: str) -> int:
    return {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}.get(severity, 99)


def _work_intake_items(workspace_root: Path, work_intake_path: str | None) -> list[dict[str, Any]]:
    if not work_intake_path:
        return []
    path = Path(work_intake_path)
    if not path.is_absolute():
        path = workspace_root / path
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _load_manual_request_scope(workspace_root: Path, source_ref: str, evidence_paths: list[str]) -> str:
    candidates: list[Path] = []
    if source_ref:
        candidates.append(workspace_root / ".cache" / "index" / "manual_requests" / f"{source_ref}.v1.json")
    for rel in evidence_paths:
        rel_path = Path(rel)
        candidates.append((workspace_root / rel_path).resolve() if not rel_path.is_absolute() else rel_path.resolve())
    for path in candidates:
        if not path.exists():
            continue
        try:
            obj = _load_json(path)
        except Exception:
            continue
        if isinstance(obj, dict):
            return str(obj.get("impact_scope") or "")
    return ""


def _fallback_extension(
    item: dict[str, Any],
    fallback_mapping: dict[str, str],
    workspace_root: Path,
) -> str:
    source_type = str(item.get("source_type") or "")
    if source_type == "MANUAL_REQUEST":
        scope = _load_manual_request_scope(
            workspace_root,
            str(item.get("source_ref") or ""),
            list(item.get("evidence_paths") or []),
        )
        key = f"{source_type}:{scope}" if scope else source_type
    else:
        key = source_type
    return str(fallback_mapping.get(key) or fallback_mapping.get(source_type) or "")


def _infer_job_kind(item: dict[str, Any]) -> str:
    source_type = str(item.get("source_type") or "")
    source_ref = str(item.get("source_ref") or "")
    title = str(item.get("title") or "")
    for text in [source_ref, title]:
        if not text:
            continue
        if "|" in text:
            head = text.split("|", 1)[0]
            if head:
                return head
        if ":" in text:
            head = text.split(":", 1)[-1]
            head = head.split("|", 1)[0]
            if head:
                return head
    if source_type == "RELEASE":
        return "RELEASE_RC"
    if source_type == "JOB_STATUS":
        return "SMOKE_FULL"
    return "PR_POLL"


def plan_auto_mode_dispatch(
    *,
    items: list[dict[str, Any]],
    policy: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    mode = str(policy.get("mode") or "mixed")
    use_selected = mode in {"selected_only", "mixed"}
    use_suggested = mode in {"suggested_only", "mixed"}

    dispatch_cfg = policy.get("dispatch") if isinstance(policy.get("dispatch"), dict) else {}
    prefer_selected = bool(dispatch_cfg.get("prefer_selected_autopilot", True))
    prefer_suggested = bool(dispatch_cfg.get("prefer_suggested_extension", True))
    fallback_mapping = dispatch_cfg.get("fallback_mapping") if isinstance(dispatch_cfg.get("fallback_mapping"), dict) else {}
    fallback_mapping = {str(k): str(v) for k, v in fallback_mapping.items() if isinstance(k, str) and isinstance(v, str)}

    candidates: list[dict[str, Any]] = []

    for item in items:
        state = str(item.get("status") or "").upper()
        if state not in {"OPEN", "PLANNED"}:
            continue
        autopilot_selected = bool(item.get("autopilot_selected", item.get("selected_autopilot", False)))
        suggested = item.get("suggested_extension") if isinstance(item.get("suggested_extension"), list) else []
        suggested_list = sorted({str(x) for x in suggested if isinstance(x, str) and x})

        extension_id = ""
        reason = ""
        if autopilot_selected and use_selected:
            reason = "selected_autopilot"
            if suggested_list and prefer_suggested:
                extension_id = suggested_list[0]
            else:
                extension_id = _fallback_extension(item, fallback_mapping, workspace_root)
        elif use_suggested and suggested_list:
            reason = "suggested_extension"
            extension_id = suggested_list[0]
        elif use_suggested and fallback_mapping:
            fallback = _fallback_extension(item, fallback_mapping, workspace_root)
            if fallback:
                reason = "fallback_mapping"
                extension_id = fallback

        if not extension_id:
            continue

        candidates.append(
            {
                "intake_id": str(item.get("intake_id") or ""),
                "bucket": str(item.get("bucket") or ""),
                "priority": str(item.get("priority") or ""),
                "severity": str(item.get("severity") or ""),
                "source_type": str(item.get("source_type") or ""),
                "source_ref": str(item.get("source_ref") or ""),
                "title": str(item.get("title") or ""),
                "autopilot_allowed": bool(item.get("autopilot_allowed", False)),
                "autopilot_selected": autopilot_selected,
                "extension_id": extension_id,
                "selection_reason": reason,
            }
        )

    candidates.sort(
        key=lambda x: (
            _priority_rank(str(x.get("priority"))),
            _severity_rank(str(x.get("severity"))),
            str(x.get("intake_id")),
        )
    )

    selected_ids: list[str] = []
    job_candidates: list[dict[str, Any]] = []
    release_candidates: list[dict[str, Any]] = []
    plan_candidates: list[dict[str, Any]] = []
    dispatched_extensions: list[str] = []

    for item in candidates:
        extension_id = str(item.get("extension_id") or "")
        dispatched_extensions.append(extension_id)
        if extension_id == "PRJ-GITHUB-OPS":
            job_candidates.append(
                {
                    "intake_id": str(item.get("intake_id") or ""),
                    "extension_id": extension_id,
                    "job_kind": _infer_job_kind(item),
                    "selection_reason": str(item.get("selection_reason") or ""),
                }
            )
            continue
        if extension_id == "PRJ-RELEASE-AUTOMATION":
            release_candidates.append(
                {
                    "intake_id": str(item.get("intake_id") or ""),
                    "extension_id": extension_id,
                    "selection_reason": str(item.get("selection_reason") or ""),
                }
            )
            continue

        if item.get("bucket") == "TICKET" and bool(item.get("autopilot_allowed", False)):
            selected_ids.append(str(item.get("intake_id") or ""))
        else:
            plan_candidates.append(item)

    dispatched_extensions = sorted({x for x in dispatched_extensions if x})
    selected_ids = sorted({x for x in selected_ids if x})

    return {
        "candidates": candidates,
        "selected_ids": selected_ids,
        "job_candidates": job_candidates,
        "release_candidates": release_candidates,
        "plan_candidates": plan_candidates,
        "dispatched_extensions": dispatched_extensions,
    }


def write_selection_file(*, workspace_root: Path, selected_ids: list[str], notes: list[str]) -> str:
    selection_path = workspace_root / ".cache" / "index" / "work_intake_selection.v1.json"
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "selected_ids": sorted({str(x) for x in selected_ids if str(x)}),
        "content_hash": _hash_text(_canonical_json(sorted({str(x) for x in selected_ids if str(x)}))),
        "notes": sorted(set(notes)),
    }
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(_dump_json(payload), encoding="utf-8")
    return str(Path(".cache") / "index" / "work_intake_selection.v1.json")


def write_plan_only(
    *,
    workspace_root: Path,
    plan_candidates: list[dict[str, Any]],
    reason: str,
) -> str:
    if not plan_candidates:
        return ""
    ids = sorted({str(item.get("intake_id") or "") for item in plan_candidates if str(item.get("intake_id") or "")})
    plan_id = _hash_text("|".join(ids))[:12]
    plan_name = f"CHG-AUTO-MODE-DISPATCH-{plan_id}.plan.json"
    plan_path = workspace_root / ".cache" / "reports" / "chg" / plan_name
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "plan_id": plan_name.replace(".plan.json", ""),
        "workspace_root": str(workspace_root),
        "reason": reason,
        "items": [
            {
                "intake_id": str(item.get("intake_id") or ""),
                "bucket": str(item.get("bucket") or ""),
                "source_type": str(item.get("source_type") or ""),
                "source_ref": str(item.get("source_ref") or ""),
                "extension_id": str(item.get("extension_id") or ""),
            }
            for item in plan_candidates
        ],
        "notes": ["PLAN_ONLY=true", "PROGRAM_LED=true"],
    }
    plan_path.write_text(_dump_json(payload), encoding="utf-8")
    md_path = plan_path.with_suffix(".plan.md")
    lines = [
        "AUTO MODE DISPATCH PLAN",
        "",
        f"Plan: {payload['plan_id']}",
        f"Reason: {reason}",
        "",
        "Items:",
    ]
    for item in payload["items"]:
        lines.append(f"- {item.get('intake_id')} {item.get('bucket')} {item.get('source_type')} {item.get('extension_id')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(Path(".cache") / "reports" / "chg" / plan_name)


def auto_mode_network_allowed(*, workspace_root: Path, policy: dict[str, Any], extension_id: str) -> tuple[bool, str]:
    gate = policy.get("network_gate") if isinstance(policy.get("network_gate"), dict) else {}
    default_network = bool(gate.get("default_network_enabled", False))
    require_extension = bool(gate.get("require_extension_policy_enable", True))
    if not default_network:
        return False, "NETWORK_DISABLED"
    if not require_extension:
        return True, "NETWORK_ALLOWED"
    if extension_id == "PRJ-GITHUB-OPS":
        policy_path = _repo_root() / "policies" / "policy_github_ops.v1.json"
        if policy_path.exists():
            try:
                obj = _load_json(policy_path)
            except Exception:
                return False, "GITHUB_POLICY_INVALID"
            if isinstance(obj, dict) and bool(obj.get("network_enabled", False)):
                return True, "NETWORK_ALLOWED"
            return False, "NETWORK_DISABLED"
    if extension_id == "PRJ-RELEASE-AUTOMATION":
        policy_path = _repo_root() / "policies" / "policy_release_automation.v1.json"
        if policy_path.exists():
            try:
                obj = _load_json(policy_path)
            except Exception:
                return False, "RELEASE_POLICY_INVALID"
            if isinstance(obj, dict):
                publish = obj.get("network_publish_enabled")
                if isinstance(publish, bool) and publish:
                    return True, "NETWORK_ALLOWED"
        return False, "NETWORK_DISABLED"
    return False, "NETWORK_DISABLED"
