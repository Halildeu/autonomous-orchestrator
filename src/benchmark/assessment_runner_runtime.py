from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_if_missing_or_same(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        raise ValueError(f"CHG_CONTENT_MISMATCH:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _load_catalog_seed(seed_path: Path, workspace_root: Path) -> dict[str, Any] | None:
    if not seed_path.exists():
        return None
    try:
        obj = _load_json(seed_path)
    except Exception:
        return None

    def _normalize_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            s = item.strip()
            if s:
                out.append(s)
        return out

    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        items = []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not item_id or not title:
            continue
        source = str(item.get("source") or "seed").strip()
        tags_raw = item.get("tags") if isinstance(item.get("tags"), list) else []
        tags = [str(t).strip() for t in tags_raw if isinstance(t, str) and t.strip()]
        summary = str(item.get("summary") or "").strip()
        evidence_expectations = _normalize_str_list(item.get("evidence_expectations"))
        remediation = _normalize_str_list(item.get("remediation"))

        payload: dict[str, Any] = {
            "id": item_id,
            "title": title,
            "source": source,
            "tags": sorted(set(tags)),
        }
        if summary:
            payload["summary"] = summary
        if evidence_expectations:
            payload["evidence_expectations"] = evidence_expectations
        if remediation:
            payload["remediation"] = remediation

        normalized.append(payload)
    normalized.sort(key=lambda entry: entry["id"])
    generated_at = str(obj.get("generated_at") or _now_iso())
    return {
        "version": "v1",
        "generated_at": generated_at,
        "workspace_root": str(workspace_root),
        "items": normalized,
    }


def _pick_first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _seed_candidates(*, workspace_root: Path, core_root: Path) -> dict[str, list[Path]]:
    return {
        "bp": [
            workspace_root / ".cache" / "inputs" / "bp_catalog.seed.v1.json",
            core_root / "docs" / "OPERATIONS" / "north_star_bp_catalog.seed.v1.json",
        ],
        "trend": [
            workspace_root / ".cache" / "inputs" / "trend_catalog.seed.v1.json",
            core_root / "docs" / "OPERATIONS" / "north_star_trend_catalog.seed.v1.json",
        ],
    }


def _write_seed_catalogs(
    *, workspace_root: Path, out_bp_catalog: Path, out_trend_catalog: Path, core_root: Path | None = None
) -> dict[str, Any]:
    core_root = core_root or _repo_root()

    candidates = _seed_candidates(workspace_root=workspace_root, core_root=core_root)
    bp_seed = _pick_first_existing(candidates.get("bp", [])) or candidates.get("bp", [None])[0]
    trend_seed = _pick_first_existing(candidates.get("trend", [])) or candidates.get("trend", [None])[0]

    bp_payload = _load_catalog_seed(bp_seed, workspace_root) if isinstance(bp_seed, Path) else None
    trend_payload = _load_catalog_seed(trend_seed, workspace_root) if isinstance(trend_seed, Path) else None
    written: list[str] = []
    if bp_payload and bp_payload.get("items"):
        _atomic_write_json(out_bp_catalog, bp_payload)
        written.append(str(out_bp_catalog))
    if trend_payload and trend_payload.get("items"):
        _atomic_write_json(out_trend_catalog, trend_payload)
        written.append(str(out_trend_catalog))
    return {
        "bp_items": len(bp_payload.get("items", [])) if bp_payload else 0,
        "trend_items": len(trend_payload.get("items", [])) if trend_payload else 0,
        "seed_paths_used": sorted(
            set(
                [
                    str(p)
                    for p in [
                        bp_seed if isinstance(bp_seed, Path) else None,
                        trend_seed if isinstance(trend_seed, Path) else None,
                    ]
                    if p
                ]
            )
        ),
        "written": sorted(set(written)),
    }


def _write_integrity_md(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# Integrity Verify Report",
        "",
        f"Generated at: {snapshot.get('generated_at', '')}",
        f"Workspace: {snapshot.get('workspace_root', '')}",
        f"Verify result: {snapshot.get('verify_on_read_result', '')}",
        f"Mismatch count: {snapshot.get('mismatch_count', 0)}",
        "",
        "Mismatches:",
    ]
    mismatches = snapshot.get("mismatches") if isinstance(snapshot, dict) else None
    if isinstance(mismatches, list) and mismatches:
        for item in mismatches:
            if isinstance(item, str) and item.strip():
                lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _draft_gap_chgs(*, workspace_root: Path, gap_register: dict[str, Any]) -> list[str]:
    gaps = gap_register.get("gaps") if isinstance(gap_register, dict) else None
    if not isinstance(gaps, list):
        return []

    safe_ids: list[str] = []
    plan_ids: list[str] = []
    for g in gaps:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        severity = g.get("severity")
        if not isinstance(gid, str):
            continue
        if severity == "low":
            safe_ids.append(gid)
        else:
            plan_ids.append(gid)

    safe_ids = sorted(set(safe_ids))
    plan_ids = sorted(set(plan_ids))
    drafted: list[str] = []
    chg_dir = workspace_root / ".cache" / "debt_chg"

    def _build_payload(chg_id: str, *, action_kind: str, file_relpath: str, note_text: str) -> dict[str, Any]:
        return {
            "id": chg_id,
            "version": "v1",
            "source": "SYSTEM_STATUS",
            "target_debt_kind": "BENCHMARK_GAP",
            "actions": [
                {
                    "kind": action_kind,
                    "file_relpath": file_relpath,
                    "note": {"text": note_text},
                }
            ],
            "safety": {"apply_scope": "INCUBATOR_ONLY", "destructive": False, "requires_review": True},
        }

    if safe_ids:
        chg_hash = _hash_bytes(("safe:" + ",".join(safe_ids)).encode("utf-8"))[:8]
        chg_id = f"CHG-GAP-SAFE-{chg_hash}"
        payload = _build_payload(
            chg_id,
            action_kind="DOC_NOTE",
            file_relpath="incubator/plans/benchmark_gap_safe.md",
            note_text="Safe-only gaps: " + ", ".join(safe_ids),
        )
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path = chg_dir / f"{chg_id}.json"
        _write_if_missing_or_same(path, content)
        drafted.append(str(path))

    if plan_ids:
        chg_hash = _hash_bytes(("plan:" + ",".join(plan_ids)).encode("utf-8"))[:8]
        chg_id = f"CHG-GAP-PLAN-{chg_hash}"
        payload = _build_payload(
            chg_id,
            action_kind="REFACTOR_HINT",
            file_relpath="incubator/plans/benchmark_gap_plan.md",
            note_text="Plan-only gaps: " + ", ".join(plan_ids),
        )
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path = chg_dir / f"{chg_id}.json"
        _write_if_missing_or_same(path, content)
        drafted.append(str(path))

    return drafted
