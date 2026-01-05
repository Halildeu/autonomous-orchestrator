from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _sha_id(seed: str) -> str:
    return sha256(seed.encode("utf-8")).hexdigest()[:16]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _resolve_workspace_path(workspace_root: Path, rel: str) -> Path | None:
    path = (workspace_root / rel).resolve()
    return path if _is_within_root(path, workspace_root) else None


@dataclass(frozen=True)
class AdvisorPolicy:
    enabled: bool
    max_suggestions: int
    forbid_kinds: list[str]
    output_path: str


def _load_policy(core_root: Path, workspace_root: Path) -> AdvisorPolicy:
    defaults = AdvisorPolicy(
        enabled=True,
        max_suggestions=50,
        forbid_kinds=["SECRET_HINT", "TENANT_IDENTITY"],
        output_path=".cache/learning/pack_advisor_suggestions.v1.json",
    )

    ws_policy = workspace_root / "policies" / "policy_advisor.v1.json"
    core_policy = core_root / "policies" / "policy_advisor.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    try:
        max_suggestions = int(obj.get("max_suggestions", defaults.max_suggestions))
    except Exception:
        max_suggestions = defaults.max_suggestions
    if max_suggestions <= 0:
        max_suggestions = defaults.max_suggestions

    raw_forbid = obj.get("forbid_kinds", defaults.forbid_kinds)
    forbid_kinds = (
        [str(x) for x in raw_forbid if isinstance(x, str) and x.strip()] if isinstance(raw_forbid, list) else []
    )
    if not forbid_kinds:
        forbid_kinds = defaults.forbid_kinds

    return AdvisorPolicy(
        enabled=enabled,
        max_suggestions=max_suggestions,
        forbid_kinds=forbid_kinds,
        output_path=str(defaults.output_path),
    )


def _load_selected_pack_ids(workspace_root: Path) -> list[str]:
    path = workspace_root / ".cache" / "index" / "pack_selection_trace.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    selected = obj.get("selected_pack_ids") if isinstance(obj, dict) else None
    ids = [x for x in selected if isinstance(x, str)] if isinstance(selected, list) else []
    return sorted(set(ids))


def _load_actions(workspace_root: Path) -> list[dict[str, Any]]:
    path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    if not path.exists():
        return []
    try:
        obj = _load_json(path)
    except Exception:
        return []
    actions = obj.get("actions") if isinstance(obj, dict) else None
    return [a for a in actions if isinstance(a, dict)] if isinstance(actions, list) else []


def _severity_rank(val: Any) -> int:
    if not isinstance(val, str):
        return 0
    return {"INFO": 1, "WARN": 2, "FAIL": 3}.get(val.upper(), 0)


def _load_pack_manifest(core_root: Path, workspace_root: Path, pack_id: str) -> dict[str, Any] | None:
    ws_path = workspace_root / "packs" / pack_id / "pack.manifest.v1.json"
    core_path = core_root / "packs" / pack_id / "pack.manifest.v1.json"
    path = ws_path if ws_path.exists() else core_path
    if not path.exists():
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def _build_suggestions(
    *,
    core_root: Path,
    workspace_root: Path,
    selected_pack_ids: list[str],
    actions: list[dict[str, Any]],
    forbid_kinds: list[str],
    max_suggestions: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    suggestions: list[dict[str, Any]] = []

    action_by_kind: dict[str, list[dict[str, Any]]] = {}
    for a in actions:
        kind = a.get("kind")
        if isinstance(kind, str):
            action_by_kind.setdefault(kind, []).append(a)

    for pack_id in selected_pack_ids:
        manifest = _load_pack_manifest(core_root, workspace_root, pack_id)
        if not manifest:
            notes.append(f"PACK_MANIFEST_MISSING:{pack_id}")
            continue
        mappings = manifest.get("improvement_mappings") if isinstance(manifest, dict) else None
        if not isinstance(mappings, list):
            continue
        for m in mappings:
            if not isinstance(m, dict):
                continue
            trigger_kind = m.get("trigger_kind")
            suggestion_kind = m.get("suggestion_kind")
            target = m.get("target")
            min_severity = m.get("min_severity", "WARN")
            if not (isinstance(trigger_kind, str) and isinstance(suggestion_kind, str) and isinstance(target, str)):
                continue
            if suggestion_kind in forbid_kinds:
                notes.append(f"FORBIDDEN_KIND:{suggestion_kind}")
                continue
            trigger_actions = action_by_kind.get(trigger_kind, [])
            if not trigger_actions:
                continue
            if _severity_rank(min_severity) == 0:
                min_severity = "WARN"
            meets = [
                a for a in trigger_actions if _severity_rank(a.get("severity")) >= _severity_rank(min_severity)
            ]
            if not meets:
                continue
            seed = f"{pack_id}:{trigger_kind}:{suggestion_kind}:{target}"
            suggestions.append(
                {
                    "id": f"SUG-{_sha_id(seed)}",
                    "pack_id": pack_id,
                    "kind": suggestion_kind,
                    "title": f"{pack_id}: {suggestion_kind}",
                    "details": f"Trigger {trigger_kind} observed; target {target}.",
                    "confidence": 0.4,
                    "evidence_refs": [".cache/roadmap_actions.v1.json"],
                    "recommended_action": f"Review {pack_id} mapping and plan {target} updates.",
                }
            )

    suggestions.sort(key=lambda s: str(s.get("id") or ""))
    if max_suggestions > 0:
        suggestions = suggestions[:max_suggestions]
    return (suggestions, notes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    dry_run = str(args.dry_run).lower() == "true"
    workspace_root = Path(args.workspace_root).resolve()
    core_root = _repo_root()

    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        print(json.dumps({"status": "SKIPPED", "reason": "DISABLED"}, sort_keys=True))
        return

    selected_pack_ids = _load_selected_pack_ids(workspace_root)
    actions = _load_actions(workspace_root)

    suggestions, notes = _build_suggestions(
        core_root=core_root,
        workspace_root=workspace_root,
        selected_pack_ids=selected_pack_ids,
        actions=actions,
        forbid_kinds=policy.forbid_kinds,
        max_suggestions=policy.max_suggestions,
    )

    safety_status = "OK"
    if notes or not selected_pack_ids:
        safety_status = "WARN"

    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "selected_pack_ids": selected_pack_ids,
        "suggestions": suggestions,
        "safety": {"status": safety_status, "notes": sorted(set(notes))},
    }

    out_rel = policy.output_path if args.out is None else str(args.out)
    out_path = _resolve_workspace_path(workspace_root, out_rel)
    if not out_path:
        raise SystemExit("Output path escapes workspace root.")

    if dry_run:
        print(json.dumps({"status": "WOULD_WRITE", "out": str(out_path), "suggestions": len(suggestions)}, sort_keys=True))
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_dump_json(report), encoding="utf-8")

    schema_path = core_root / "schemas" / "pack-advisor-suggestions.schema.json"
    if schema_path.exists():
        schema = _load_json(schema_path)
        Draft202012Validator(schema).validate(report)

    print(json.dumps({"status": "OK", "out": str(out_path), "suggestions": len(suggestions)}, sort_keys=True))


if __name__ == "__main__":
    main()
