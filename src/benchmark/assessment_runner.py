from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.benchmark.gap_engine import build_gap_register, build_gap_summary_md


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    target.relative_to(workspace_root)


def _resolve_output_path(workspace_root: Path, rel_path: str) -> Path:
    rel = Path(rel_path).as_posix()
    out = (workspace_root / rel).resolve()
    _ensure_inside_workspace(workspace_root, out)
    return out


def _fail(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "FAIL", "error_code": code}
    if message:
        payload["message"] = message
    if details:
        payload["details"] = details
    return payload


def _load_policy(*, core_root: Path, workspace_root: Path) -> dict[str, Any]:
    ws_policy = workspace_root / "policies" / "policy_benchmark.v1.json"
    core_policy = core_root / "policies" / "policy_benchmark.v1.json"
    path = ws_policy if ws_policy.exists() else core_policy
    if not path.exists():
        return {
            "version": "v1",
            "enabled": True,
            "cursor_mode": "hash",
            "outputs": {
                "north_star_catalog": ".cache/index/north_star_catalog.v1.json",
                "assessment": ".cache/index/assessment.v1.json",
                "assessment_cursor": ".cache/index/assessment_cursor.v1.json",
                "scorecard_json": ".cache/reports/benchmark_scorecard.v1.json",
                "scorecard_md": ".cache/reports/benchmark_scorecard.v1.md",
                "gap_register": ".cache/index/gap_register.v1.json",
                "gap_summary_md": ".cache/reports/gap_summary.v1.md",
            },
            "max_controls": 2000,
        }
    return _load_json(path)


def _collect_standard_packs(*, core_root: Path, workspace_root: Path) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    sources = [("core", core_root / "packs" / "standards"), ("workspace", workspace_root / "packs" / "standards")]
    for source, base in sources:
        if not base.exists():
            continue
        for manifest in sorted(base.rglob("pack.manifest.v1.json")):
            try:
                obj = _load_json(manifest)
            except Exception:
                continue
            pack_id = obj.get("pack_id") if isinstance(obj, dict) else None
            if not isinstance(pack_id, str):
                continue
            record = {
                "pack_id": pack_id,
                "version": obj.get("version"),
                "source": source,
                "manifest_path": manifest,
            }
            if pack_id in records and source == "workspace":
                records[pack_id] = record
            elif pack_id not in records:
                records[pack_id] = record
    return [records[k] for k in sorted(records)]


def _load_controls_metrics(pack_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    controls: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    controls_path = pack_dir / "controls.v1.json"
    metrics_path = pack_dir / "metrics.v1.json"
    if controls_path.exists():
        try:
            obj = _load_json(controls_path)
            items = obj.get("controls") if isinstance(obj, dict) else None
            if isinstance(items, list):
                for c in items:
                    if isinstance(c, dict) and isinstance(c.get("id"), str):
                        controls.append(c)
        except Exception:
            pass
    if metrics_path.exists():
        try:
            obj = _load_json(metrics_path)
            items = obj.get("metrics") if isinstance(obj, dict) else None
            if isinstance(items, list):
                for m in items:
                    if isinstance(m, dict) and isinstance(m.get("id"), str):
                        metrics.append(m)
        except Exception:
            pass
    return (controls, metrics)


def _inputs_sha256(files: list[Path], *, core_root: Path, workspace_root: Path) -> str:
    parts: list[str] = []
    for path in sorted(files, key=lambda p: p.as_posix()):
        if not path.exists() or not path.is_file():
            continue
        data = path.read_bytes()
        try:
            rel = path.relative_to(core_root)
        except Exception:
            try:
                rel = path.relative_to(workspace_root)
            except Exception:
                rel = path
        parts.append(f"{rel.as_posix()}:{_hash_bytes(data)}")
    payload = "\n".join(parts).encode("utf-8")
    return _hash_bytes(payload)


def _write_if_missing_or_same(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        raise ValueError(f"CHG_CONTENT_MISMATCH:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def run_assessment(*, workspace_root: Path, dry_run: bool) -> dict[str, Any]:
    core_root = _repo_root()
    policy = _load_policy(core_root=core_root, workspace_root=workspace_root)
    if not isinstance(policy, dict) or not policy.get("enabled", True):
        return {"status": "SKIPPED", "reason": "policy_disabled"}

    outputs = policy.get("outputs") if isinstance(policy, dict) else None
    if not isinstance(outputs, dict):
        return _fail("BENCHMARK_SCHEMA_INVALID", "policy.outputs missing or invalid")

    try:
        out_catalog = _resolve_output_path(workspace_root, str(outputs.get("north_star_catalog")))
        out_assessment = _resolve_output_path(workspace_root, str(outputs.get("assessment")))
        out_cursor = _resolve_output_path(workspace_root, str(outputs.get("assessment_cursor")))
        out_scorecard_json = _resolve_output_path(workspace_root, str(outputs.get("scorecard_json")))
        out_scorecard_md = _resolve_output_path(workspace_root, str(outputs.get("scorecard_md")))
        out_gap_register = _resolve_output_path(workspace_root, str(outputs.get("gap_register")))
        out_gap_md = _resolve_output_path(workspace_root, str(outputs.get("gap_summary_md")))
    except Exception as e:
        return _fail("BENCHMARK_WRITE_VIOLATION", "output path escapes workspace_root", {"error": str(e)[:200]})

    core_standards = list((core_root / "packs" / "standards").rglob("pack.manifest.v1.json"))
    if not core_standards:
        return _fail("BENCHMARK_INPUT_MISSING", "no standard packs found", {"path": "packs/standards"})

    packs = _collect_standard_packs(core_root=core_root, workspace_root=workspace_root)
    controls: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    warnings: list[str] = []
    input_files: list[Path] = []

    for pack in packs:
        manifest_path = pack.get("manifest_path")
        if isinstance(manifest_path, Path):
            input_files.append(manifest_path)
            pack_dir = manifest_path.parent
            c_list, m_list = _load_controls_metrics(pack_dir)
            for c in c_list:
                c_item = dict(c)
                c_item["pack_id"] = pack.get("pack_id")
                controls.append(c_item)
            for m in m_list:
                m_item = dict(m)
                m_item["pack_id"] = pack.get("pack_id")
                metrics.append(m_item)
            if not c_list and not m_list:
                warnings.append(f"pack_missing_controls_or_metrics:{pack.get('pack_id')}")
            controls_path = pack_dir / "controls.v1.json"
            metrics_path = pack_dir / "metrics.v1.json"
            if controls_path.exists():
                input_files.append(controls_path)
            if metrics_path.exists():
                input_files.append(metrics_path)

    controls = sorted(controls, key=lambda x: str(x.get("id") or ""))
    metrics = sorted(metrics, key=lambda x: str(x.get("id") or ""))

    inputs_sha = _inputs_sha256(input_files, core_root=core_root, workspace_root=workspace_root)
    cursor_obj = None
    if out_cursor.exists():
        try:
            cursor_obj = _load_json(out_cursor)
        except Exception:
            cursor_obj = None

    if isinstance(cursor_obj, dict) and cursor_obj.get("inputs_sha256") == inputs_sha:
        if out_catalog.exists() and out_assessment.exists() and out_scorecard_json.exists() and out_gap_register.exists():
            return {
                "status": "OK",
                "unchanged": True,
                "out": str(out_assessment),
                "packs": len(packs),
                "controls": len(controls),
                "metrics": len(metrics),
            }

    catalog = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "packs": [
            {
                "pack_id": p.get("pack_id"),
                "version": p.get("version"),
                "source": p.get("source"),
                "control_count": len([c for c in controls if c.get("pack_id") == p.get("pack_id")]),
                "metric_count": len([m for m in metrics if m.get("pack_id") == p.get("pack_id")]),
            }
            for p in packs
        ],
        "controls": controls,
        "metrics": metrics,
        "warnings": sorted(set(warnings)),
    }

    assessment = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "packs": len(packs),
        "controls": len(controls),
        "metrics": len(metrics),
        "status": "OK" if controls else "WARN",
        "warnings": sorted(set(warnings)),
    }

    gap_register = build_gap_register(controls=controls, metrics=metrics)
    gap_summary_md = build_gap_summary_md(gap_register=gap_register)

    schema_path = core_root / "schemas" / "gap.record.schema.json"
    if schema_path.exists():
        try:
            schema = _load_json(schema_path)
            Draft202012Validator(schema).validate(gap_register)
        except Exception as e:
            return _fail("BENCHMARK_SCHEMA_INVALID", "gap register schema validation failed", {"error": str(e)[:200]})

    scorecard = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "packs": len(packs),
        "controls": len(controls),
        "metrics": len(metrics),
        "status": assessment.get("status"),
    }
    scorecard_md = "\n".join(
        [
            "# Benchmark Scorecard",
            "",
            f"Packs: {len(packs)}",
            f"Controls: {len(controls)}",
            f"Metrics: {len(metrics)}",
            f"Status: {assessment.get('status')}",
        ]
    ) + "\n"

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "out": str(out_assessment),
            "packs": len(packs),
            "controls": len(controls),
            "metrics": len(metrics),
            "inputs_sha256": inputs_sha,
            "outputs": [
                str(out_catalog),
                str(out_assessment),
                str(out_cursor),
                str(out_scorecard_json),
                str(out_scorecard_md),
                str(out_gap_register),
                str(out_gap_md),
            ],
        }

    for path in [out_catalog, out_assessment, out_cursor, out_scorecard_json, out_scorecard_md, out_gap_register, out_gap_md]:
        path.parent.mkdir(parents=True, exist_ok=True)

    out_catalog.write_text(json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_assessment.write_text(json.dumps(assessment, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_scorecard_json.write_text(json.dumps(scorecard, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_scorecard_md.write_text(scorecard_md, encoding="utf-8")
    out_gap_register.write_text(json.dumps(gap_register, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    out_gap_md.write_text(gap_summary_md, encoding="utf-8")

    outputs_sha = _hash_bytes(json.dumps(assessment, sort_keys=True).encode("utf-8"))
    cursor = {
        "version": "v1",
        "inputs_sha256": inputs_sha,
        "outputs_sha256": outputs_sha,
        "generated_at": _now_iso(),
    }
    out_cursor.write_text(json.dumps(cursor, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    drafted = _draft_gap_chgs(workspace_root=workspace_root, gap_register=gap_register)

    return {
        "status": "OK",
        "out": str(out_assessment),
        "packs": len(packs),
        "controls": len(controls),
        "metrics": len(metrics),
        "gap_chg_drafts": len(drafted),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    dry_run = str(args.dry_run).lower() == "true"
    workspace_root = Path(args.workspace_root).resolve()

    try:
        payload = run_assessment(workspace_root=workspace_root, dry_run=dry_run)
    except Exception as e:
        payload = _fail("BENCHMARK_INTERNAL_ERROR", "unexpected error", {"error": str(e)[:200]})

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = payload.get("status") if isinstance(payload, dict) else None
    return 0 if status in {"OK", "WOULD_WRITE", "SKIPPED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
