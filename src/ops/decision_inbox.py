from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_inbox_paths() -> tuple[Path, Path]:
    return (Path(".cache") / "index" / "decision_inbox.v1.json", Path(".cache") / "reports" / "decision_inbox.v1.md")


def _resolve_inbox_paths(output_paths: dict[str, Any]) -> tuple[Path, Path, Path, Path]:
    decision_path = Path(str(output_paths.get("decision_inbox_path") or ".cache/index/decision_inbox.v1.json"))
    decision_md_path = Path(str(output_paths.get("decision_inbox_md_path") or ".cache/reports/decision_inbox.v1.md"))
    canonical_path, canonical_md_path = _canonical_inbox_paths()
    return (decision_path, decision_md_path, canonical_path, canonical_md_path)


def _seed_dir(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "decision_seeds"


def _load_decision_seeds(workspace_root: Path) -> list[dict[str, Any]]:
    seeds_dir = _seed_dir(workspace_root)
    if not seeds_dir.exists():
        return []
    seeds: list[dict[str, Any]] = []
    for path in sorted(seeds_dir.glob("SEED-*.v1.json")):
        try:
            obj = _load_json(path)
        except Exception:
            continue
        if isinstance(obj, dict):
            obj["_seed_path"] = str(path)
            seeds.append(obj)
    return seeds


def _load_policy(core_root: Path, workspace_root: Path) -> dict[str, Any]:
    core_path = core_root / "policies" / "policy_decision_inbox.v1.json"
    policy: dict[str, Any] = {
        "version": "v1",
        "limits": {"max_items_per_run": 20, "dedup_window_hours": 24},
        "mapping": {"decision_kind_map": {}, "default_decision_kind": "UNKNOWN"},
        "output_paths": {
            "decision_inbox_path": ".cache/index/decision_inbox.v1.json",
            "decision_inbox_md_path": ".cache/reports/decision_inbox.v1.md",
            "decisions_applied_path": ".cache/index/decisions_applied.v1.jsonl",
            "selection_path": ".cache/index/work_intake_selection.v1.json",
            "policy_overrides_dir": ".cache/policy_overrides",
        },
    }
    if core_path.exists():
        try:
            obj = _load_json(core_path)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            policy.update(obj)
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_decision_inbox.override.v1.json"
    if override_path.exists():
        try:
            obj = _load_json(override_path)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            policy.update(obj)
    return policy


def _load_decisions_applied(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _load_work_intake_index(workspace_root: Path) -> dict[str, dict[str, Any]]:
    path = workspace_root / ".cache" / "index" / "work_intake.v1.json"
    if not path.exists():
        return {}
    try:
        obj = _load_json(path)
    except Exception:
        return {}
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        intake_id = item.get("intake_id")
        if isinstance(intake_id, str) and intake_id:
            index[intake_id] = item
    return index


def _is_doc_only(intake_index: dict[str, dict[str, Any]], intake_id: str) -> bool:
    item = intake_index.get(intake_id, {})
    scope = item.get("impact_scope") if isinstance(item, dict) else None
    if isinstance(scope, str) and scope.strip().lower().replace("_", "-") == "doc-only":
        return True
    reason = item.get("autopilot_reason") if isinstance(item, dict) else None
    if isinstance(reason, str) and reason.strip().upper() == "DOC_ONLY":
        return True
    return False


def _decision_kind_for(reason: str, mapping: dict[str, Any]) -> str:
    kind_map = mapping.get("decision_kind_map") if isinstance(mapping.get("decision_kind_map"), dict) else {}
    default_kind = str(mapping.get("default_decision_kind") or "UNKNOWN")
    if isinstance(kind_map, dict) and reason in kind_map:
        return str(kind_map.get(reason) or default_kind)
    return default_kind


_ALLOWED_DECISION_KINDS = {
    "ROUTE_OVERRIDE",
    "AUTO_APPLY_ALLOW",
    "NETWORK_ENABLE",
    "SCOPE_CONFIRM",
    "UNKNOWN",
}


def _normalize_decision_kind(kind: str) -> str:
    if kind in _ALLOWED_DECISION_KINDS:
        return kind
    return "UNKNOWN"


def _option(option_id: str, title: str, changes_ref: str = "") -> dict[str, Any]:
    return {"option_id": option_id, "title": title, "changes_ref": changes_ref}


def _options_for(kind: str) -> tuple[list[dict[str, Any]], str]:
    if kind == "AUTO_APPLY_ALLOW":
        return (
            [
                _option("A", "Keep blocked"),
                _option("B", "Allow auto-apply"),
            ],
            "A",
        )
    if kind == "NETWORK_ENABLE":
        return (
            [
                _option("A", "Keep network disabled"),
                _option("B", "Enable network for this extension"),
            ],
            "A",
        )
    if kind == "ROUTE_OVERRIDE":
        return (
            [
                _option("A", "Keep current routing"),
                _option("B", "Override routing"),
            ],
            "A",
        )
    return ([_option("A", "Keep blocked")], "A")


def _default_option_title(decision: dict[str, Any]) -> str:
    default_id = str(decision.get("default_option_id") or "")
    options = decision.get("options") if isinstance(decision.get("options"), list) else []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        if str(opt.get("option_id") or "") != default_id:
            continue
        return str(opt.get("title") or "")
    return ""


def _default_option_matches(decision: dict[str, Any], expected_title: str) -> bool:
    return _default_option_title(decision) == expected_title


def run_decision_inbox_build(*, workspace_root: Path) -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    output_paths = policy.get("output_paths") if isinstance(policy.get("output_paths"), dict) else {}
    decision_path, decision_md_path, canonical_path, canonical_md_path = _resolve_inbox_paths(output_paths)
    decisions_applied_path = Path(str(output_paths.get("decisions_applied_path") or ".cache/index/decisions_applied.v1.jsonl"))
    exec_path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
    exec_obj: dict[str, Any] = {}
    exec_missing = not exec_path.exists()
    if not exec_missing:
        try:
            exec_obj = _load_json(exec_path)
        except Exception:
            exec_obj = {}
    entries = exec_obj.get("entries") if isinstance(exec_obj, dict) else None
    if not isinstance(entries, list):
        entries = []

    mapping = policy.get("mapping") if isinstance(policy.get("mapping"), dict) else {}
    limit = int(policy.get("limits", {}).get("max_items_per_run", 20) or 20)

    decisions: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "") != "SKIPPED":
            continue
        if str(entry.get("skip_reason") or "") != "DECISION_NEEDED":
            continue
        intake_id = str(entry.get("intake_id") or "")
        reason = str(entry.get("autopilot_reason") or entry.get("reason") or "DECISION_NEEDED")
        decision_kind = _normalize_decision_kind(_decision_kind_for(reason, mapping))
        decision_id = _hash_text(f"{intake_id}:{decision_kind}:{reason}")
        options, default_option_id = _options_for(decision_kind)
        evidence_paths = []
        if isinstance(entry.get("evidence_paths"), list):
            evidence_paths.extend([str(p) for p in entry.get("evidence_paths") if isinstance(p, str)])
        evidence_paths.append(str(Path(".cache") / "reports" / "work_intake_exec_ticket.v1.json"))
        decisions.append(
            {
                "decision_id": decision_id,
                "source_intake_id": intake_id,
                "bucket": str(entry.get("bucket") or ""),
                "decision_kind": decision_kind,
                "question": f"Decision required for {intake_id}",
                "options": options,
                "default_option_id": default_option_id,
                "why_blocked": reason,
                "evidence_paths": sorted({p for p in evidence_paths if p}),
                "expires_at": None,
            }
        )

    seed_items = _load_decision_seeds(workspace_root)
    for seed in seed_items:
        decision_kind = _normalize_decision_kind(str(seed.get("decision_kind") or seed.get("kind") or "UNKNOWN"))
        target = str(seed.get("target") or "")
        seed_id = str(seed.get("seed_id") or _hash_text(f"{workspace_root}:{decision_kind}:{target}"))
        source_intake_id = str(seed.get("source_intake_id") or f"SEED:{target or seed_id}")
        bucket = str(seed.get("bucket") or "PROJECT")
        options, default_option_id = _options_for(decision_kind)
        evidence_paths = []
        seed_path = seed.get("_seed_path")
        if isinstance(seed_path, str) and seed_path:
            evidence_paths.append(_rel_path(workspace_root, Path(seed_path)))
        decisions.append(
            {
                "decision_id": seed_id,
                "source_intake_id": source_intake_id,
                "bucket": bucket,
                "decision_kind": decision_kind,
                "question": f"Decision seed for {target or source_intake_id}",
                "options": options,
                "default_option_id": default_option_id,
                "why_blocked": "DECISION_SEED",
                "evidence_paths": sorted({p for p in evidence_paths if p}),
                "expires_at": None,
            }
        )

    applied_ids: set[str] = set()
    applied_path = workspace_root / decisions_applied_path
    if applied_path.exists():
        for record in _load_decisions_applied(applied_path):
            decision_id = record.get("decision_id") if isinstance(record, dict) else None
            if isinstance(decision_id, str) and decision_id:
                applied_ids.add(decision_id)
    if applied_ids:
        decisions = [d for d in decisions if str(d.get("decision_id") or "") not in applied_ids]

    def _bucket_rank(val: str) -> int:
        order = {"INCIDENT": 0, "PROJECT": 1, "TICKET": 2, "ROADMAP": 3}
        return int(order.get(val, 9))

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in decisions:
        decision_id = str(item.get("decision_id") or "")
        if not decision_id or decision_id in seen:
            continue
        seen.add(decision_id)
        deduped.append(item)
    decisions = sorted(
        deduped,
        key=lambda d: (
            _bucket_rank(str(d.get("bucket") or "")),
            str(d.get("decision_kind") or ""),
            str(d.get("source_intake_id") or ""),
            str(d.get("decision_id") or ""),
        ),
    )[: max(0, limit)]
    counts_by_kind: dict[str, int] = {}
    for item in decisions:
        kind = str(item.get("decision_kind") or "UNKNOWN")
        counts_by_kind[kind] = int(counts_by_kind.get(kind, 0)) + 1

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "items": decisions,
        "counts": {"total": len(decisions), "by_kind": {k: counts_by_kind[k] for k in sorted(counts_by_kind)}},
        "notes": ["PROGRAM_LED=true", "NO_WAIT=true"],
    }

    out_md_lines = ["DECISION INBOX", "", f"Total: {len(decisions)}", ""]
    for item in decisions:
        out_md_lines.append(
            f"- {item.get('decision_id')} intake={item.get('source_intake_id')} kind={item.get('decision_kind')}"
        )

    for path in sorted({decision_path, canonical_path}, key=lambda p: p.as_posix()):
        out_path = workspace_root / path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_dump_json(payload), encoding="utf-8")
    for path in sorted({decision_md_path, canonical_md_path}, key=lambda p: p.as_posix()):
        out_md_path = workspace_root / path
        out_md_path.parent.mkdir(parents=True, exist_ok=True)
        out_md_path.write_text("\n".join(out_md_lines) + "\n", encoding="utf-8")

    status = "OK" if decisions else "IDLE"
    return {
        "status": status,
        "decision_inbox_path": str(canonical_path),
        "decision_inbox_md_path": str(canonical_md_path),
        "decisions_count": len(decisions),
        "error_code": "EXEC_REPORT_MISSING" if (exec_missing and not decisions) else None,
    }


def run_decision_seed(*, workspace_root: Path, decision_kind: str, target: str) -> dict[str, Any]:
    normalized_kind = _normalize_decision_kind(str(decision_kind))
    seed_id = _hash_text(f"{workspace_root}:{normalized_kind}:{target}")
    payload = {
        "version": "v1",
        "seed_id": seed_id,
        "decision_kind": normalized_kind,
        "target": target,
        "created_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "notes": ["seeded=true", "PROGRAM_LED=true"],
    }
    seed_path = _seed_dir(workspace_root) / f"SEED-{seed_id}.v1.json"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(_dump_json(payload), encoding="utf-8")
    return {
        "status": "OK",
        "seed_id": seed_id,
        "decision_kind": normalized_kind,
        "target": target,
        "seed_path": str(Path(".cache") / "index" / "decision_seeds" / seed_path.name),
    }


def _write_decisions_applied(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _update_selection_file(*, workspace_root: Path, intake_id: str, selection_path: Path) -> None:
    selected: list[str] = []
    if selection_path.exists():
        try:
            obj = _load_json(selection_path)
        except Exception:
            obj = None
        if isinstance(obj, dict) and isinstance(obj.get("selected_ids"), list):
            selected = [str(x) for x in obj.get("selected_ids") if isinstance(x, str)]
    if intake_id and intake_id not in selected:
        selected.append(intake_id)
    selected = sorted(set(selected))
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "selected_ids": selected,
        "content_hash": _hash_text("\n".join(selected)),
    }
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(_dump_json(payload), encoding="utf-8")


def _write_policy_override(*, workspace_root: Path, overrides_dir: Path) -> str:
    overrides_dir.mkdir(parents=True, exist_ok=True)
    override_path = overrides_dir / "policy_github_ops.override.v1.json"
    payload = {
        "version": "v1",
        "network_enabled": True,
        "live_gate": {"enabled": True},
    }
    override_path.write_text(_dump_json(payload), encoding="utf-8")
    return str(override_path.relative_to(workspace_root))


def run_decision_inbox_show(*, workspace_root: Path) -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    output_paths = policy.get("output_paths") if isinstance(policy.get("output_paths"), dict) else {}
    decision_path, decision_md_path, canonical_path, canonical_md_path = _resolve_inbox_paths(output_paths)

    inbox_path = workspace_root / decision_path
    md_path = workspace_root / decision_md_path
    if not inbox_path.exists() or not md_path.exists():
        run_decision_inbox_build(workspace_root=workspace_root)

    inbox_path = workspace_root / decision_path
    if not inbox_path.exists():
        inbox_path = workspace_root / canonical_path
    md_path = workspace_root / decision_md_path
    if not md_path.exists():
        md_path = workspace_root / canonical_md_path

    if not inbox_path.exists():
        return {
            "status": "IDLE",
            "error_code": "DECISION_INBOX_MISSING",
            "workspace_root": str(workspace_root),
            "decision_inbox_path": str(canonical_path),
            "decision_inbox_md_path": str(canonical_md_path),
            "decisions_count": 0,
            "decisions": [],
        }
    try:
        inbox = _load_json(inbox_path)
    except Exception:
        return {
            "status": "WARN",
            "error_code": "DECISION_INBOX_INVALID",
            "workspace_root": str(workspace_root),
            "decision_inbox_path": str(canonical_path),
            "decision_inbox_md_path": str(canonical_md_path),
            "decisions_count": 0,
            "decisions": [],
        }

    items = inbox.get("items") if isinstance(inbox, dict) else None
    items_list = items if isinstance(items, list) else []
    counts = inbox.get("counts") if isinstance(inbox, dict) else None
    pending_count = int(counts.get("total") or 0) if isinstance(counts, dict) else len(items_list)
    by_kind = counts.get("by_kind") if isinstance(counts, dict) else {}
    if not isinstance(by_kind, dict):
        by_kind = {}

    decisions = []
    for item in items_list:
        if not isinstance(item, dict):
            continue
        decisions.append(
            {
                "decision_id": str(item.get("decision_id") or ""),
                "decision_kind": str(item.get("decision_kind") or ""),
                "source_intake_id": str(item.get("source_intake_id") or ""),
                "default_option_id": str(item.get("default_option_id") or ""),
            }
        )

    status = "OK" if pending_count else "IDLE"
    return {
        "status": status,
        "error_code": None,
        "workspace_root": str(workspace_root),
        "decision_inbox_path": str(canonical_path),
        "decision_inbox_md_path": str(canonical_md_path),
        "decisions_count": pending_count,
        "pending_by_kind": {k: int(by_kind[k]) for k in sorted(by_kind) if isinstance(by_kind[k], int)},
        "decisions": decisions,
    }


def run_decision_apply_bulk(
    *, workspace_root: Path, mode: str, decision_ids: list[str] | None = None
) -> dict[str, Any]:
    mode = str(mode or "").strip().lower()
    if mode not in {"safe_defaults", "decision_ids"}:
        return {"status": "WARN", "error_code": "INVALID_MODE"}

    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    output_paths = policy.get("output_paths") if isinstance(policy.get("output_paths"), dict) else {}
    decision_path, decision_md_path, canonical_path, canonical_md_path = _resolve_inbox_paths(output_paths)
    decisions_applied_path = Path(str(output_paths.get("decisions_applied_path") or ".cache/index/decisions_applied.v1.jsonl"))

    inbox_path = workspace_root / decision_path
    if not inbox_path.exists():
        inbox_path = workspace_root / canonical_path
    if not inbox_path.exists():
        return {
            "status": "IDLE",
            "error_code": "DECISION_INBOX_MISSING",
            "workspace_root": str(workspace_root),
            "decision_inbox_path": str(canonical_path),
            "decision_inbox_md_path": str(canonical_md_path),
            "applied_count": 0,
            "skipped_count": 0,
        }
    try:
        inbox = _load_json(inbox_path)
    except Exception:
        return {
            "status": "WARN",
            "error_code": "DECISION_INBOX_INVALID",
            "workspace_root": str(workspace_root),
            "decision_inbox_path": str(canonical_path),
            "decision_inbox_md_path": str(canonical_md_path),
            "applied_count": 0,
            "skipped_count": 0,
        }

    items = inbox.get("items") if isinstance(inbox, dict) else None
    items_list = items if isinstance(items, list) else []
    counts = inbox.get("counts") if isinstance(inbox, dict) else None
    pending_before = int(counts.get("total") or 0) if isinstance(counts, dict) else len(items_list)

    safe_defaults = {
        "NETWORK_ENABLE": {"default_title": "Keep network disabled", "require_doc_only": False},
        "ROUTE_OVERRIDE": {"default_title": "Keep current routing", "require_doc_only": False},
        "AUTO_APPLY_ALLOW": {"default_title": "Keep blocked", "require_doc_only": True},
    }

    intake_index = _load_work_intake_index(workspace_root)
    requested_ids: list[str] = []
    seen_requested: set[str] = set()
    for raw in decision_ids or []:
        if not isinstance(raw, str):
            continue
        decision_id = str(raw).strip()
        if not decision_id or decision_id in seen_requested:
            continue
        seen_requested.add(decision_id)
        requested_ids.append(decision_id)
    requested_set = set(requested_ids)

    apply_candidates: list[dict[str, Any]] = []
    skipped_by_reason: dict[str, int] = {}
    if mode == "decision_ids":
        if not requested_ids:
            return {
                "status": "IDLE",
                "error_code": "NO_DECISION_IDS",
                "workspace_root": str(workspace_root),
                "decision_inbox_path": str(canonical_path),
                "decision_inbox_md_path": str(canonical_md_path),
                "applied_count": 0,
                "skipped_count": 0,
            }
        for item in items_list:
            if not isinstance(item, dict):
                continue
            decision_id = str(item.get("decision_id") or "")
            if decision_id and decision_id in requested_set:
                apply_candidates.append(item)
        found_ids = {str(x.get("decision_id") or "") for x in apply_candidates if isinstance(x, dict)}
        missing = [i for i in requested_ids if i not in found_ids]
        if missing:
            skipped_by_reason["DECISION_NOT_FOUND"] = len(missing)
    else:
        for item in items_list:
            if not isinstance(item, dict):
                continue
            decision_kind = str(item.get("decision_kind") or "")
            safe_cfg = safe_defaults.get(decision_kind)
            if not safe_cfg:
                skipped_by_reason["NOT_ALLOWED_KIND"] = skipped_by_reason.get("NOT_ALLOWED_KIND", 0) + 1
                continue
            if safe_cfg.get("require_doc_only"):
                intake_id = str(item.get("source_intake_id") or "")
                if intake_id.startswith("SEED:") or not _is_doc_only(intake_index, intake_id):
                    skipped_by_reason["NOT_DOC_ONLY"] = skipped_by_reason.get("NOT_DOC_ONLY", 0) + 1
                    continue
            if not _default_option_matches(item, str(safe_cfg.get("default_title") or "")):
                skipped_by_reason["DEFAULT_NOT_RECOMMENDED"] = skipped_by_reason.get("DEFAULT_NOT_RECOMMENDED", 0) + 1
                continue
            if not str(item.get("default_option_id") or ""):
                skipped_by_reason["DEFAULT_OPTION_MISSING"] = skipped_by_reason.get("DEFAULT_OPTION_MISSING", 0) + 1
                continue
            apply_candidates.append(item)

    applied: list[dict[str, Any]] = []
    applied_count = 0
    for item in apply_candidates:
        if not isinstance(item, dict):
            continue
        decision_id = str(item.get("decision_id") or "")
        option_id = str(item.get("default_option_id") or "")
        if not decision_id or not option_id:
            skipped_by_reason["INVALID_DECISION"] = skipped_by_reason.get("INVALID_DECISION", 0) + 1
            continue
        res = run_decision_apply(workspace_root=workspace_root, decision_id=decision_id, option_id=option_id)
        if res.get("status") == "OK":
            applied_count += 1
            applied.append(
                {
                    "decision_id": decision_id,
                    "decision_kind": str(res.get("decision_kind") or ""),
                    "option_id": option_id,
                }
            )
        else:
            skipped_by_reason["APPLY_FAILED"] = skipped_by_reason.get("APPLY_FAILED", 0) + 1

    inbox_after = run_decision_inbox_build(workspace_root=workspace_root)
    pending_after = int(inbox_after.get("decisions_count") or 0) if isinstance(inbox_after, dict) else 0

    report_rel = Path(".cache") / "reports" / "decision_apply_bulk.v1.json"
    report_path = workspace_root / report_rel
    skipped_count = sum(int(v) for v in skipped_by_reason.values() if isinstance(v, int))
    status = "OK"
    if applied_count == 0 and skipped_count == 0:
        status = "IDLE"
    elif skipped_count:
        status = "WARN"
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "mode": mode,
        "decision_inbox_path": str(canonical_path),
        "decision_inbox_md_path": str(canonical_md_path),
        "decisions_applied_path": str(decisions_applied_path),
        "pending_decisions_before": int(pending_before),
        "pending_decisions_after": int(pending_after),
        "applied_count": int(applied_count),
        "skipped_count": int(skipped_count),
        "skipped_by_reason": {k: int(skipped_by_reason[k]) for k in sorted(skipped_by_reason)},
        "applied_decisions": applied,
        "requested_decision_ids": requested_ids,
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
        "report_path": str(report_rel),
    }
    if applied_count == 0 and skipped_count == 0:
        payload["error_code"] = "NO_DECISIONS_APPLIED"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_dump_json(payload), encoding="utf-8")
    return payload


def run_decision_apply(*, workspace_root: Path, decision_id: str, option_id: str) -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root, workspace_root)
    output_paths = policy.get("output_paths") if isinstance(policy.get("output_paths"), dict) else {}
    decision_path, _, canonical_path, _ = _resolve_inbox_paths(output_paths)
    decisions_applied_path = Path(str(output_paths.get("decisions_applied_path") or ".cache/index/decisions_applied.v1.jsonl"))
    selection_path = Path(str(output_paths.get("selection_path") or ".cache/index/work_intake_selection.v1.json"))
    overrides_dir = Path(str(output_paths.get("policy_overrides_dir") or ".cache/policy_overrides"))

    inbox_path = workspace_root / decision_path
    if not inbox_path.exists():
        inbox_path = workspace_root / canonical_path
    if not inbox_path.exists():
        return {"status": "IDLE", "error_code": "DECISION_INBOX_MISSING"}
    try:
        inbox = _load_json(inbox_path)
    except Exception:
        return {"status": "IDLE", "error_code": "DECISION_INBOX_INVALID"}
    items = inbox.get("items") if isinstance(inbox, dict) else None
    if not isinstance(items, list):
        return {"status": "IDLE", "error_code": "DECISION_INBOX_EMPTY"}

    decision = next((i for i in items if isinstance(i, dict) and str(i.get("decision_id")) == decision_id), None)
    if not decision:
        return {"status": "IDLE", "error_code": "DECISION_NOT_FOUND"}

    decision_kind = str(decision.get("decision_kind") or "UNKNOWN")
    source_intake_id = str(decision.get("source_intake_id") or "")
    applied_at = _now_iso()
    record = {
        "decision_id": decision_id,
        "decision_kind": decision_kind,
        "source_intake_id": source_intake_id,
        "option_id": option_id,
        "applied_at": applied_at,
        "notes": ["PROGRAM_LED=true"],
    }

    applied_path = workspace_root / decisions_applied_path
    _write_decisions_applied(applied_path, record)

    selection_written = ""
    policy_override_written = ""
    if decision_kind == "AUTO_APPLY_ALLOW" and option_id and option_id not in {"A", "KEEP"}:
        selection_written = str(selection_path)
        _update_selection_file(
            workspace_root=workspace_root,
            intake_id=source_intake_id,
            selection_path=workspace_root / selection_path,
        )
    if decision_kind == "NETWORK_ENABLE" and option_id and option_id not in {"A", "KEEP"}:
        policy_override_written = _write_policy_override(
            workspace_root=workspace_root,
            overrides_dir=workspace_root / overrides_dir,
        )

    return {
        "status": "OK",
        "decision_id": decision_id,
        "decision_kind": decision_kind,
        "option_id": option_id,
        "decisions_applied_path": str(decisions_applied_path),
        "selection_path": selection_written,
        "policy_override_path": policy_override_written,
    }
