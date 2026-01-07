from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _hash_request_id(*, text: str, artifact_type: str, domain: str, kind: str, tenant_id: str | None) -> str:
    base = "|".join([artifact_type.strip(), domain.strip(), kind.strip(), (tenant_id or "").strip(), text])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def build_manual_request(
    *,
    text: str,
    artifact_type: str,
    domain: str,
    kind: str = "unspecified",
    impact_scope: str = "workspace-only",
    requires_core_change: bool | None = None,
    tenant_id: str | None = None,
    source_type: str = "human",
    source_channel: str | None = None,
    source_user_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    now_iso: str | None = None,
) -> tuple[str, dict[str, Any], str]:
    normalized_text = _normalize_text(text)
    digest = _hash_request_id(
        text=normalized_text,
        artifact_type=artifact_type,
        domain=domain,
        kind=kind,
        tenant_id=tenant_id,
    )
    date = (now_iso or _now_iso()).split("T", 1)[0].replace("-", "")
    request_id = f"REQ-{date}-{digest[:12]}"

    req: dict[str, Any] = {
        "version": "v1",
        "request_id": request_id,
        "created_at": now_iso or _now_iso(),
        "source": {"type": source_type},
        "artifact_type": artifact_type,
        "domain": domain,
        "kind": kind,
        "impact_scope": impact_scope,
        "text": text,
    }
    if requires_core_change is not None:
        req["requires_core_change"] = bool(requires_core_change)
    if source_channel:
        req["source"]["channel"] = source_channel
    if source_user_id:
        req["source"]["user_id"] = source_user_id
    if tenant_id:
        req["tenant_id"] = tenant_id
    if attachments:
        cleaned = []
        for item in attachments:
            if not isinstance(item, dict):
                continue
            kind_val = item.get("kind")
            value = item.get("value")
            if isinstance(kind_val, str) and isinstance(value, str) and kind_val and value:
                cleaned.append({"kind": kind_val, "value": value})
        if cleaned:
            req["attachments"] = cleaned
    if constraints and isinstance(constraints, dict):
        filtered: dict[str, Any] = {}
        for key in ("layer", "side_effect", "requires_core_change"):
            if key in constraints:
                filtered[key] = constraints.get(key)
        if requires_core_change is not None and "requires_core_change" not in filtered:
            filtered["requires_core_change"] = bool(requires_core_change)
        if filtered:
            req["constraints"] = filtered
    if tags:
        req["tags"] = [str(t) for t in tags if str(t).strip()]

    return request_id, req, digest


def submit_manual_request(
    *,
    workspace_root: Path,
    text: str,
    artifact_type: str,
    domain: str,
    kind: str = "unspecified",
    impact_scope: str = "workspace-only",
    requires_core_change: bool | None = None,
    tenant_id: str | None = None,
    source_type: str = "human",
    source_channel: str | None = None,
    source_user_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    now = _now_iso()
    request_id, req, digest = build_manual_request(
        text=text,
        artifact_type=artifact_type,
        domain=domain,
        kind=kind,
        impact_scope=impact_scope,
        requires_core_change=requires_core_change,
        tenant_id=tenant_id,
        source_type=source_type,
        source_channel=source_channel,
        source_user_id=source_user_id,
        attachments=attachments,
        constraints=constraints,
        tags=tags,
        now_iso=now,
    )

    manual_dir = workspace_root / ".cache" / "index" / "manual_requests"
    out_path = manual_dir / f"{request_id}.v1.json"
    report_path = workspace_root / ".cache" / "reports" / "manual_request_submit.v1.json"
    _ensure_inside_workspace(workspace_root, out_path)
    _ensure_inside_workspace(workspace_root, report_path)

    result = {
        "status": "OK",
        "request_id": request_id,
        "stored_path": str(Path(".cache") / "index" / "manual_requests" / f"{request_id}.v1.json"),
        "report_path": str(Path(".cache") / "reports" / "manual_request_submit.v1.json"),
        "text_present": bool(text.strip()),
        "text_bytes": len(text.encode("utf-8")),
        "attachments_count": len(req.get("attachments") or []),
        "request_hash": digest,
        "notes": [],
    }

    if dry_run:
        result["status"] = "IDLE"
        result["notes"].append("dry_run=true")
        return result

    manual_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(req, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return result
