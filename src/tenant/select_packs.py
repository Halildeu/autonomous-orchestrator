from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _sha256_obj(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(payload).hexdigest()


def _parse_bool(val: str) -> bool:
    v = str(val).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


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
class PackSelectionPolicy:
    enabled: bool
    match_fields: list[str]
    max_candidates: int
    tie_break: str
    hard_conflict_behavior: str
    soft_conflict_behavior: str
    trace_enabled: bool
    trace_out_path: str


def _load_policy(core_root: Path, workspace_root: Path) -> PackSelectionPolicy:
    defaults = PackSelectionPolicy(
        enabled=True,
        match_fields=["intent", "artifact_type"],
        max_candidates=10,
        tie_break="pack_id_lexicographic",
        hard_conflict_behavior="fail",
        soft_conflict_behavior="warn",
        trace_enabled=True,
        trace_out_path=".cache/index/pack_selection_trace.v1.json",
    )

    ws_policy = workspace_root / "policies" / "policy_pack_selection.v1.json"
    core_policy = core_root / "policies" / "policy_pack_selection.v1.json"
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
    shortlist = obj.get("shortlist")
    if not isinstance(shortlist, dict):
        shortlist = {}
    match_fields = [
        str(f)
        for f in shortlist.get("match_fields", defaults.match_fields)
        if isinstance(f, str)
    ]
    if not match_fields:
        match_fields = defaults.match_fields
    try:
        max_candidates = int(shortlist.get("max_candidates", defaults.max_candidates))
    except Exception:
        max_candidates = defaults.max_candidates
    if max_candidates <= 0:
        max_candidates = defaults.max_candidates

    tie_break = obj.get("tie_break")
    if not isinstance(tie_break, dict):
        tie_break = {}
    mode = tie_break.get("mode", defaults.tie_break)
    if mode != "pack_id_lexicographic":
        mode = defaults.tie_break

    hard_conflict_behavior = obj.get("hard_conflict_behavior", defaults.hard_conflict_behavior)
    if hard_conflict_behavior not in {"fail"}:
        hard_conflict_behavior = defaults.hard_conflict_behavior

    soft_conflict_behavior = obj.get("soft_conflict_behavior", defaults.soft_conflict_behavior)
    if soft_conflict_behavior not in {"warn"}:
        soft_conflict_behavior = defaults.soft_conflict_behavior

    selection_trace = obj.get("selection_trace")
    if not isinstance(selection_trace, dict):
        selection_trace = {}
    trace_enabled = bool(selection_trace.get("enabled", defaults.trace_enabled))
    out_path = selection_trace.get("out_path", defaults.trace_out_path)
    if not isinstance(out_path, str) or not out_path.strip():
        out_path = defaults.trace_out_path

    return PackSelectionPolicy(
        enabled=enabled,
        match_fields=match_fields,
        max_candidates=max_candidates,
        tie_break=mode,
        hard_conflict_behavior=hard_conflict_behavior,
        soft_conflict_behavior=soft_conflict_behavior,
        trace_enabled=trace_enabled,
        trace_out_path=str(out_path),
    )


def _load_pack_index(workspace_root: Path) -> dict[str, Any]:
    index_path = workspace_root / ".cache" / "index" / "pack_capability_index.v1.json"
    if not index_path.exists():
        raise SystemExit("Missing pack index: .cache/index/pack_capability_index.v1.json")
    try:
        return _load_json(index_path)
    except Exception as e:
        raise SystemExit("Invalid pack index JSON.") from e


def _build_shortlist(
    *,
    packs: list[dict[str, Any]],
    intent: str,
    artifact_type: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for p in packs:
        pack_id = p.get("pack_id")
        if not isinstance(pack_id, str):
            continue
        reasons: list[str] = []
        intents = p.get("intents")
        if isinstance(intents, list) and intent and intent in intents:
            reasons.append("intent_match")
        if not reasons and artifact_type:
            formats = p.get("formats")
            workflows = p.get("workflows")
            if isinstance(formats, list) and formats:
                reasons.append("format_fallback")
            elif isinstance(workflows, list) and workflows:
                reasons.append("workflow_fallback")
        if reasons:
            candidates.append({"pack_id": pack_id, "reason": reasons})
    candidates.sort(key=lambda c: str(c.get("pack_id")))
    return candidates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--intent", required=True)
    ap.add_argument("--artifact-type", default="")
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args()

    dry_run = _parse_bool(args.dry_run)
    workspace_root = Path(args.workspace_root).resolve()
    core_root = _repo_root()

    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        print(json.dumps({"status": "SKIPPED", "reason": "DISABLED"}, sort_keys=True))
        return

    index_obj = _load_pack_index(workspace_root)
    packs = index_obj.get("packs") if isinstance(index_obj, dict) else None
    pack_list = [p for p in packs if isinstance(p, dict)] if isinstance(packs, list) else []

    hard_conflicts = index_obj.get("hard_conflicts") if isinstance(index_obj, dict) else None
    soft_conflicts = index_obj.get("soft_conflicts") if isinstance(index_obj, dict) else None
    hard_count = len(hard_conflicts) if isinstance(hard_conflicts, list) else 0
    soft_count = len(soft_conflicts) if isinstance(soft_conflicts, list) else 0

    candidates = _build_shortlist(
        packs=pack_list,
        intent=str(args.intent),
        artifact_type=str(args.artifact_type),
    )
    shortlist = candidates[: policy.max_candidates]
    selected_pack_ids: list[str] = []
    if shortlist:
        selected_pack_ids.append(str(shortlist[0].get("pack_id")))

    trace = {
        "version": "v1",
        "workspace_root": str(workspace_root),
        "input": {"intent": str(args.intent), "artifact_type": str(args.artifact_type)},
        "shortlist": shortlist,
        "selected_pack_ids": selected_pack_ids,
        "conflicts": {"hard": hard_count, "soft": soft_count},
    }
    trace_hash = _sha256_obj(trace)
    trace["hashes"] = {"trace_sha256": trace_hash}

    out_path: Path | None = None
    if policy.trace_enabled:
        out_path = _resolve_workspace_path(workspace_root, policy.trace_out_path)
        if not out_path:
            raise SystemExit("Selection trace path escapes workspace root.")

    if dry_run:
        print(
            json.dumps(
                {
                    "status": "WOULD_WRITE",
                    "out": str(out_path) if out_path else "",
                    "selected": len(selected_pack_ids),
                    "candidates": len(shortlist),
                },
                sort_keys=True,
            )
        )
        return

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_dump_json(trace), encoding="utf-8")

    if hard_count and policy.hard_conflict_behavior == "fail":
        print(json.dumps({"status": "FAIL", "hard_conflicts": hard_count}, sort_keys=True))
        raise SystemExit("HARD_CONFLICT")

    print(
        json.dumps(
            {
                "status": "OK",
                "out": str(out_path) if out_path else "",
                "selected": len(selected_pack_ids),
                "candidates": len(shortlist),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
