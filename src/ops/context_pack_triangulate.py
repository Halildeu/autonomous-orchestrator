from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return str(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_policy(core_root: Path) -> dict[str, Any]:
    policy_path = core_root / "policies" / "policy_context_triangulation.v1.json"
    default_policy = {
        "version": "v1",
        "enabled": True,
        "merge": {
            "strategy": "field_majority",
            "min_agreement": 2,
            "record_disagreements": True,
            "record_assumptions": True,
        },
        "inputs": {"require_three": True},
    }
    if not policy_path.exists():
        return default_policy
    try:
        obj = _load_json(policy_path)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return default_policy
    return default_policy


def _load_response(path: Path) -> dict[str, Any]:
    try:
        obj = _load_json(path)
    except Exception:
        return {"_invalid": True}
    if isinstance(obj, dict):
        return obj
    return {"value": obj}


def _candidate_meta(response: dict[str, Any], response_path: str) -> dict[str, Any]:
    provider_id = response.get("provider_id") if isinstance(response.get("provider_id"), str) else "unknown"
    model_id = response.get("model_id") if isinstance(response.get("model_id"), str) else "unknown"
    content_hash = _hash_text(_canonical_json(response))
    return {
        "provider_id": provider_id or "unknown",
        "model_id": model_id or "unknown",
        "response_path": response_path,
        "content_hash": content_hash,
    }


def _majority_value(values: list[Any], min_agreement: int) -> tuple[bool, Any | None, str | None]:
    signatures: list[tuple[str, Any]] = [(_canonical_json(value), value) for value in values]
    counts: dict[str, int] = {}
    for sig, _ in signatures:
        counts[sig] = counts.get(sig, 0) + 1
    if not counts:
        return False, None, None
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top_sig, top_count = ranked[0]
    if top_count >= min_agreement:
        for sig, value in signatures:
            if sig == top_sig:
                return True, value, top_sig
    return False, None, None


def _merge_candidates(responses: list[dict[str, Any]], *, min_agreement: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    keys: set[str] = set()
    for response in responses:
        keys.update([k for k in response.keys() if isinstance(k, str)])
    merged: dict[str, Any] = {}
    disagreements: list[dict[str, Any]] = []
    assumptions: list[str] = []

    for key in sorted(keys):
        values = [resp.get(key) for resp in responses]
        ok, value, sig = _majority_value(values, min_agreement)
        if ok:
            if value is None:
                continue
            merged[key] = value
            continue
        non_null = [val for val in values if val is not None]
        value_hashes = sorted({_hash_text(_canonical_json(val)) for val in non_null})
        disagreements.append(
            {
                "field": key,
                "value_hashes": value_hashes,
                "present_count": len(non_null),
            }
        )
        assumptions.append(f"manual_resolution_required:{key}")

    assumptions = sorted(assumptions)
    return merged, disagreements, assumptions


def _build_context_pack(
    *,
    workspace_root: Path,
    merged: dict[str, Any],
    candidates_rel: str,
    merge_rel: str,
) -> dict[str, Any]:
    context_pack_id = _hash_text(_canonical_json(merged))
    now = _now_iso()
    pointer_candidates = {
        "scope": "workspace",
        "path": candidates_rel,
        "kind": "context_triangulation",
        "label": "candidates",
    }
    pointer_merge = {
        "scope": "workspace",
        "path": merge_rel,
        "kind": "context_triangulation",
        "label": "merge",
    }
    return {
        "version": "v1",
        "generated_at": now,
        "context_pack_id": context_pack_id,
        "workspace_root": str(workspace_root),
        "request_ref": {
            "request_id": "CONTEXT_TRIANGULATION",
            "scope": "workspace",
            "path": candidates_rel,
            "kind": "triangulation",
        },
        "request_meta": {
            "artifact_type": "context_triangulation",
            "domain": "context",
            "kind": "define",
            "source_type": "merge",
            "created_at": now,
            "attachments_count": 0,
            "text_bytes": 0,
        },
        "define": {
            "context_refs": [],
            "stakeholders_refs": [],
            "scope_refs": [],
            "criteria_refs": [],
            "architecture_refs": [],
            "decision_refs": [],
        },
        "measure_raw": {},
        "eval": {},
        "gap": {},
        "pdca": {},
        "intake": {},
        "routing": {
            "chosen_bucket": "TICKET",
            "chosen_action": "NOOP",
            "recommended_ops": [],
            "output_format_ids": [],
        },
        "guardrails": {
            "core_lock": "ENABLED",
            "layer_boundary": "ENABLED",
            "network_allowed": False,
            "side_effect_max": "NONE",
        },
        "evidence_refs": [pointer_candidates, pointer_merge],
        "notes": [
            "TRIANGULATION_DEFINE_ONLY=true",
            f"merged_fields={len(merged)}",
            "PROGRAM_LED=true",
        ],
    }


def run_context_pack_triangulate(
    *,
    workspace_root: Path,
    responses: list[str],
    out: str | None = None,
) -> dict[str, Any]:
    core_root = Path(__file__).resolve().parents[2]
    policy = _load_policy(core_root)
    inputs_cfg = policy.get("inputs") if isinstance(policy.get("inputs"), dict) else {}
    require_three = bool(inputs_cfg.get("require_three", True))
    if require_three and len(responses) != 3:
        return {
            "status": "IDLE",
            "error_code": "RESPONSES_REQUIRED",
            "notes": ["require_three=true"],
        }

    workspace_root = workspace_root.resolve()
    resolved_paths: list[Path] = []
    for resp in responses:
        resp_path = Path(str(resp))
        if not resp_path.is_absolute():
            candidate = (workspace_root / resp_path).resolve()
            if candidate.exists():
                resp_path = candidate
            else:
                resp_path = (core_root / resp_path).resolve()
        resolved_paths.append(resp_path)

    resolved_paths = sorted(resolved_paths, key=lambda p: p.as_posix())
    responses_obj: list[dict[str, Any]] = [_load_response(path) for path in resolved_paths]

    candidates_rel: list[dict[str, Any]] = []
    for response, path in zip(responses_obj, resolved_paths, strict=False):
        rel = _rel_to_workspace(path, workspace_root)
        candidates_rel.append(_candidate_meta(response, rel))

    candidates_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "candidates": sorted(
            candidates_rel, key=lambda item: (item.get("provider_id", ""), item.get("model_id", ""), item.get("response_path", ""))
        ),
    }

    merge_cfg = policy.get("merge") if isinstance(policy.get("merge"), dict) else {}
    min_agreement = int(merge_cfg.get("min_agreement", 2) or 2)
    merged, disagreements, assumptions = _merge_candidates(responses_obj, min_agreement=min_agreement)
    merge_payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "merge_rule": "field_majority",
        "majority_threshold": min_agreement,
        "candidates": [
            {"response_path": c.get("response_path", ""), "content_hash": c.get("content_hash", "")}
            for c in candidates_payload.get("candidates", [])
        ],
        "merged": merged,
        "disagreements": sorted(disagreements, key=lambda item: item.get("field", "")),
        "assumptions": sorted(assumptions),
    }

    candidates_path = workspace_root / ".cache" / "index" / "context_pack_candidates.v1.json"
    merge_path = workspace_root / ".cache" / "index" / "context_pack_merge.v1.json"
    context_pack_path = workspace_root / ".cache" / "index" / "context_pack.v1.json"
    if out:
        out_path = Path(str(out))
        context_pack_path = (workspace_root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()

    candidates_path.parent.mkdir(parents=True, exist_ok=True)
    merge_path.parent.mkdir(parents=True, exist_ok=True)
    context_pack_path.parent.mkdir(parents=True, exist_ok=True)

    candidates_path.write_text(json.dumps(candidates_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    merge_path.write_text(json.dumps(merge_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    candidates_rel_path = str(Path(".cache") / "index" / "context_pack_candidates.v1.json")
    merge_rel_path = str(Path(".cache") / "index" / "context_pack_merge.v1.json")
    context_pack_payload = _build_context_pack(
        workspace_root=workspace_root,
        merged=merged,
        candidates_rel=candidates_rel_path,
        merge_rel=merge_rel_path,
    )
    context_pack_path.write_text(
        json.dumps(context_pack_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "OK",
        "candidates_path": candidates_rel_path,
        "merge_path": merge_rel_path,
        "context_pack_path": _rel_to_workspace(context_pack_path, workspace_root),
        "disagreements": len(merge_payload.get("disagreements", [])),
        "assumptions": len(merge_payload.get("assumptions", [])),
    }
