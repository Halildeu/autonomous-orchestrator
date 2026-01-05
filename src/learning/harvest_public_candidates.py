from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.roadmap import sanitize


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    # src/learning/harvest_public_candidates.py -> repo root
    return Path(__file__).resolve().parents[2]


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected true|false")


@dataclass(frozen=True)
class HarvestPolicy:
    enabled: bool
    output_path: str
    cursor_path: str
    incremental: bool
    window_max_dlq_items: int
    window_max_days: int
    forbid_patterns: list[str]
    max_candidates: int
    min_evidence_refs_per_candidate: int
    on_fail: str


def _load_policy(core_root: Path) -> HarvestPolicy:
    path = core_root / "policies" / "policy_harvest.v1.json"
    defaults = HarvestPolicy(
        enabled=True,
        output_path=".cache/learning/public_candidates.v1.json",
        cursor_path=".cache/learning/harvest_cursor.v1.json",
        incremental=True,
        window_max_dlq_items=200,
        window_max_days=7,
        forbid_patterns=["Beykent"],
        max_candidates=200,
        min_evidence_refs_per_candidate=1,
        on_fail="block",
    )
    if not path.exists():
        return defaults
    try:
        obj = _load_json(path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    output_path = obj.get("output_path", defaults.output_path)
    if not isinstance(output_path, str) or not output_path.strip():
        output_path = defaults.output_path

    cursor_path = obj.get("cursor_path", defaults.cursor_path)
    if not isinstance(cursor_path, str) or not cursor_path.strip():
        cursor_path = defaults.cursor_path

    incremental = bool(obj.get("incremental", defaults.incremental))
    window = obj.get("window", {})
    if not isinstance(window, dict):
        window = {}
    max_dlq_items = window.get("max_dlq_items", defaults.window_max_dlq_items)
    try:
        max_dlq_items_i = int(max_dlq_items)
    except Exception:
        max_dlq_items_i = defaults.window_max_dlq_items
    if max_dlq_items_i < 0:
        max_dlq_items_i = defaults.window_max_dlq_items

    max_days = window.get("max_days", defaults.window_max_days)
    try:
        max_days_i = int(max_days)
    except Exception:
        max_days_i = defaults.window_max_days
    if max_days_i < 0:
        max_days_i = defaults.window_max_days

    raw_patterns = obj.get("forbid_patterns", defaults.forbid_patterns)
    forbid_patterns = (
        [str(x) for x in raw_patterns if isinstance(x, str) and x.strip()] if isinstance(raw_patterns, list) else []
    )
    if not forbid_patterns:
        forbid_patterns = defaults.forbid_patterns

    max_candidates = obj.get("max_candidates", defaults.max_candidates)
    try:
        max_candidates_i = int(max_candidates)
    except Exception:
        max_candidates_i = defaults.max_candidates
    if max_candidates_i < 0:
        max_candidates_i = defaults.max_candidates

    min_refs = obj.get("min_evidence_refs_per_candidate", defaults.min_evidence_refs_per_candidate)
    try:
        min_refs_i = int(min_refs)
    except Exception:
        min_refs_i = defaults.min_evidence_refs_per_candidate
    if min_refs_i < 0:
        min_refs_i = defaults.min_evidence_refs_per_candidate

    on_fail = obj.get("on_fail", defaults.on_fail)
    if on_fail not in {"block", "warn"}:
        on_fail = defaults.on_fail

    policy = HarvestPolicy(
        enabled=enabled,
        output_path=str(output_path),
        cursor_path=str(cursor_path),
        incremental=bool(incremental),
        window_max_dlq_items=int(max_dlq_items_i),
        window_max_days=int(max_days_i),
        forbid_patterns=forbid_patterns,
        max_candidates=int(max_candidates_i),
        min_evidence_refs_per_candidate=int(min_refs_i),
        on_fail=str(on_fail),
    )
    return _apply_smoke_overrides(policy)


def _apply_smoke_overrides(policy: HarvestPolicy) -> HarvestPolicy:
    if os.environ.get("SMOKE_MODE") != "1":
        return policy
    max_items = min(policy.window_max_dlq_items, 20)
    max_days = min(policy.window_max_days, 1)
    return HarvestPolicy(
        enabled=policy.enabled,
        output_path=policy.output_path,
        cursor_path=policy.cursor_path,
        incremental=policy.incremental,
        window_max_dlq_items=max_items,
        window_max_days=max_days,
        forbid_patterns=policy.forbid_patterns,
        max_candidates=policy.max_candidates,
        min_evidence_refs_per_candidate=policy.min_evidence_refs_per_candidate,
        on_fail=policy.on_fail,
    )


def _load_catalog_pack_ids(workspace_root: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    pack_ids: list[str] = []
    path = workspace_root / ".cache" / "index" / "catalog.v1.json"
    if not path.exists():
        return (pack_ids, ["CATALOG_MISSING"])
    try:
        obj = _load_json(path)
    except Exception:
        return (pack_ids, ["CATALOG_INVALID_JSON"])
    packs = obj.get("packs") if isinstance(obj, dict) else None
    if not isinstance(packs, list):
        return (pack_ids, ["CATALOG_INVALID_SHAPE"])
    for p in packs:
        if isinstance(p, dict) and isinstance(p.get("pack_id"), str):
            pack_ids.append(p["pack_id"])
    pack_ids = sorted(set(pack_ids))
    return (pack_ids, warnings)


def _load_formats_ids(workspace_root: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    ids: list[str] = []
    path = workspace_root / ".cache" / "index" / "formats.v1.json"
    if not path.exists():
        return (ids, ["FORMATS_INDEX_MISSING"])
    try:
        obj = _load_json(path)
    except Exception:
        return (ids, ["FORMATS_INDEX_INVALID_JSON"])
    formats = obj.get("formats") if isinstance(obj, dict) else None
    if not isinstance(formats, list):
        return (ids, ["FORMATS_INDEX_INVALID_SHAPE"])
    for f in formats:
        if isinstance(f, dict) and isinstance(f.get("id"), str):
            ids.append(f["id"])
    ids = sorted(set(ids))
    return (ids, warnings)


def _load_action_kind_counts(workspace_root: Path) -> tuple[dict[str, int], list[str]]:
    warnings: list[str] = []
    path = workspace_root / ".cache" / "roadmap_actions.v1.json"
    if not path.exists():
        return ({}, ["ACTIONS_MISSING"])
    try:
        obj = _load_json(path)
    except Exception:
        return ({}, ["ACTIONS_INVALID_JSON"])
    actions = obj.get("actions") if isinstance(obj, dict) else None
    if not isinstance(actions, list):
        return ({}, ["ACTIONS_INVALID_SHAPE"])
    counts: dict[str, int] = {}
    for a in actions:
        if not isinstance(a, dict):
            continue
        kind = a.get("kind")
        if not isinstance(kind, str) or not kind:
            continue
        counts[kind] = counts.get(kind, 0) + 1
    return (dict(sorted(counts.items(), key=lambda kv: kv[0])), warnings)


def _parse_dlq_datetime(name: str) -> datetime | None:
    if len(name) < 8 or not name[:8].isdigit():
        return None
    date_part = name[:8]
    time_part = "000000"
    if len(name) >= 15 and name[8] in {"-", "_"} and name[9:15].isdigit():
        time_part = name[9:15]
    try:
        return datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _scan_workspace_dlq(
    workspace_root: Path,
    *,
    max_items: int,
    max_days: int,
    last_filename: str | None,
) -> tuple[int, dict[str, int], dict[str, int], str | None]:
    dlq_dir = workspace_root / "dlq"
    if not dlq_dir.exists() or not dlq_dir.is_dir():
        return (0, {}, {}, None)
    count = 0
    by_stage: dict[str, int] = {}
    by_error: dict[str, int] = {}
    paths = sorted(dlq_dir.glob("*.json"), key=lambda x: x.name, reverse=True)
    newest_name = paths[0].name if paths else None
    cutoff = None
    if max_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(max_days))
    for p in paths:
        if last_filename and p.name == last_filename:
            break
        if cutoff is not None:
            dt = _parse_dlq_datetime(p.name)
            if dt is not None and dt < cutoff:
                break
        if not p.is_file():
            continue
        if max_items > 0 and count >= int(max_items):
            break
        count += 1
        try:
            obj = _load_json(p)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        stage = obj.get("stage")
        error_code = obj.get("error_code")
        if isinstance(stage, str) and stage:
            by_stage[stage] = by_stage.get(stage, 0) + 1
        if isinstance(error_code, str) and error_code:
            by_error[error_code] = by_error.get(error_code, 0) + 1
    return (int(count), dict(sorted(by_stage.items())), dict(sorted(by_error.items())), newest_name)


def _load_cursor(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        obj = _load_json(path)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_cursor(path: Path, cursor: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(_dump_json(cursor), encoding="utf-8")
    tmp.replace(path)


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()
    return sha256(data).hexdigest()


def _redact_strings(obj: Any, patterns: list[str]) -> tuple[Any, int]:
    if isinstance(obj, str):
        out = obj
        removed = 0
        for pat in patterns:
            if pat and pat in out:
                occurrences = out.count(pat)
                removed += occurrences
                out = out.replace(pat, "[REDACTED]")
        return (out, removed)
    if isinstance(obj, list):
        total = 0
        out_list: list[Any] = []
        for item in obj:
            new_item, removed = _redact_strings(item, patterns)
            total += removed
            out_list.append(new_item)
        return (out_list, total)
    if isinstance(obj, dict):
        total = 0
        out_dict: dict[str, Any] = {}
        for k in sorted(obj.keys(), key=lambda x: str(x)):
            v = obj[k]
            new_v, removed = _redact_strings(v, patterns)
            total += removed
            out_dict[str(k)] = new_v
        return (out_dict, total)
    return (obj, 0)


def _validate_public_candidates_bundle(core_root: Path, bundle: dict[str, Any]) -> list[str]:
    schema_path = core_root / "schemas" / "public-candidates.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING:schemas/public-candidates.schema.json"]
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(bundle), key=lambda e: e.json_path)
    msgs: list[str] = []
    for err in errors[:25]:
        where = err.json_path or "$"
        msgs.append(f"{where}: {err.message}")
    return msgs


def build_public_candidates(
    *, workspace_root: Path, core_root: Path | None = None
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    core_root = core_root or _repo_root()
    policy = _load_policy(core_root)
    warnings: list[str] = []

    cursor_path = (workspace_root / policy.cursor_path).resolve()
    cursor = _load_cursor(cursor_path) if policy.incremental else None
    last_dlq_filename = cursor.get("last_dlq_filename") if isinstance(cursor, dict) else None
    if not isinstance(last_dlq_filename, str) or not last_dlq_filename.strip():
        last_dlq_filename = None

    pack_ids, pack_warn = _load_catalog_pack_ids(workspace_root)
    warnings.extend(pack_warn)
    fmt_ids, fmt_warn = _load_formats_ids(workspace_root)
    warnings.extend(fmt_warn)
    action_counts, actions_warn = _load_action_kind_counts(workspace_root)
    warnings.extend(actions_warn)
    dlq_count, dlq_stage, dlq_err, newest_dlq = _scan_workspace_dlq(
        workspace_root,
        max_items=int(policy.window_max_dlq_items),
        max_days=int(policy.window_max_days),
        last_filename=last_dlq_filename,
    )
    if newest_dlq is None and isinstance(last_dlq_filename, str):
        newest_dlq = last_dlq_filename

    candidates: list[dict[str, Any]] = []

    if fmt_ids:
        candidates.append(
            {
                "kind": "FORMAT_HINT",
                "key": "formats_present",
                "value": {"format_ids": fmt_ids},
                "confidence": 0.6,
                "evidence_refs": [".cache/index/formats.v1.json"],
            }
        )
    if pack_ids:
        candidates.append(
            {
                "kind": "PACK_HINT",
                "key": "packs_present",
                "value": {"pack_ids": pack_ids},
                "confidence": 0.6,
                "evidence_refs": [".cache/index/catalog.v1.json"],
            }
        )
    if action_counts:
        candidates.append(
            {
                "kind": "FLAKY_HINT",
                "key": "action_kinds_counts",
                "value": {"counts": action_counts},
                "confidence": 0.3,
                "evidence_refs": [".cache/roadmap_actions.v1.json"],
            }
        )
    if dlq_count > 0:
        candidates.append(
            {
                "kind": "FLAKY_HINT",
                "key": "dlq_counts",
                "value": {"dlq_items": dlq_count, "by_stage": dlq_stage, "by_error_code": dlq_err},
                "confidence": 0.2,
                "evidence_refs": ["dlq/*.json"],
            }
        )

    # Deterministic ordering and truncation.
    candidates.sort(key=lambda c: (str(c.get("kind") or ""), str(c.get("key") or "")))
    if policy.max_candidates >= 0:
        candidates = candidates[: int(policy.max_candidates)]

    bundle: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root.resolve()),
        "source_counts": {"evidence_runs": 0, "dlq_items": int(dlq_count)},
        "candidates": candidates,
        "sanitization": {"status": "OK", "removed_tokens_count": 0, "notes": []},
    }

    # Redaction step (fail-closed if policy says block and any tokens are removed).
    patterns = [p for p in policy.forbid_patterns if isinstance(p, str) and p.strip()]
    redacted, removed = _redact_strings(bundle, patterns)
    if not isinstance(redacted, dict):
        redacted = bundle
        removed = 0
    bundle = redacted
    bundle["sanitization"]["removed_tokens_count"] = int(removed)  # type: ignore[index]
    if removed > 0:
        bundle["sanitization"]["status"] = "FAIL" if policy.on_fail == "block" else "WARN"  # type: ignore[index]
        bundle["sanitization"]["notes"] = ["FORBIDDEN_PATTERNS_REDACTED"]  # type: ignore[index]

    # Schema validation (deterministic).
    schema_errors = _validate_public_candidates_bundle(core_root, bundle)
    if schema_errors:
        bundle["sanitization"]["status"] = "FAIL"  # type: ignore[index]
        bundle["sanitization"]["notes"] = ["SCHEMA_INVALID"]  # type: ignore[index]
        warnings.append("SCHEMA_INVALID")

    # Evidence ref minimum check.
    min_refs = int(policy.min_evidence_refs_per_candidate)
    if min_refs > 0:
        for c in candidates:
            refs = c.get("evidence_refs") if isinstance(c, dict) else None
            if not (isinstance(refs, list) and len(refs) >= min_refs):
                bundle["sanitization"]["status"] = "FAIL"  # type: ignore[index]
                bundle["sanitization"]["notes"] = ["EVIDENCE_REFS_TOO_FEW"]  # type: ignore[index]
                warnings.append("EVIDENCE_REFS_TOO_FEW")
                break

    # Additional scan for email/token markers (reuse sanitize.py) on the JSON bytes we are about to write.
    run_index_sha = _file_sha256(workspace_root / ".cache" / "index" / "run_index.v1.json")
    cursor_info = {
        "cursor_path": str(cursor_path),
        "last_dlq_filename": newest_dlq,
        "last_run_index_sha256": run_index_sha,
    }

    return (bundle, sorted(set(str(x) for x in warnings if isinstance(x, str) and x)), cursor_info)


def harvest_to_path(
    *,
    workspace_root: Path,
    out_path: Path,
    dry_run: bool,
    core_root: Path | None = None,
) -> dict[str, Any]:
    core_root = core_root or _repo_root()
    policy = _load_policy(core_root)
    bundle, warnings, cursor_info = build_public_candidates(workspace_root=workspace_root, core_root=core_root)

    candidates = bundle.get("candidates") if isinstance(bundle, dict) else None
    candidates_count = len(candidates) if isinstance(candidates, list) else 0

    payload = _dump_json(bundle)
    bytes_estimate = len(payload.encode("utf-8"))

    status = bundle.get("sanitization", {}).get("status") if isinstance(bundle, dict) else None  # type: ignore[union-attr]
    if status == "FAIL" and policy.on_fail == "block":
        return {
            "status": "FAIL",
            "error_code": "SANITIZE_VIOLATION",
            "out": str(out_path),
            "candidates": int(candidates_count),
            "warnings": warnings,
            "sanitization": bundle.get("sanitization"),
        }

    if dry_run:
        return {"status": "WOULD_WRITE", "out": str(out_path), "candidates": int(candidates_count), "bytes_estimate": int(bytes_estimate)}

    if not _is_within_root(out_path, workspace_root):
        return {"status": "FAIL", "error_code": "OUTSIDE_WORKSPACE_ROOT", "out": str(out_path)}

    tmp_dir = (out_path.parent / f".tmp_harvest_{os.getpid()}").resolve()
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = tmp_dir / out_path.name
        tmp_file.write_text(payload, encoding="utf-8")
        ok_scan, findings = sanitize.scan_directory(root=tmp_dir, forbidden_tokens=policy.forbid_patterns)
        if not ok_scan:
            try:
                tmp_file.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            return {
                "status": "FAIL",
                "error_code": "SANITIZE_VIOLATION",
                "out": str(out_path),
                "findings": [{"path": f.path, "rule": f.rule} for f in findings[:10]],
            }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.replace(out_path)
    finally:
        try:
            for p in sorted(tmp_dir.rglob("*"), key=lambda x: x.as_posix(), reverse=True):
                if p.is_file():
                    p.unlink(missing_ok=True)  # type: ignore[arg-type]
            tmp_dir.rmdir()
        except Exception:
            pass

    cursor_written = False
    if policy.incremental:
        cursor_path = (workspace_root / policy.cursor_path).resolve()
        if _is_within_root(cursor_path, workspace_root):
            cursor_obj = {
                "version": "v1",
                "last_dlq_filename": cursor_info.get("last_dlq_filename"),
                "last_run_index_sha256": cursor_info.get("last_run_index_sha256"),
                "updated_at": _now_iso8601(),
            }
            try:
                _write_cursor(cursor_path, cursor_obj)
                cursor_written = True
            except Exception:
                cursor_written = False

    return {
        "status": "OK",
        "out": str(out_path),
        "candidates": int(candidates_count),
        "warnings": warnings,
        "sanitization": bundle.get("sanitization"),
        "cursor_written": bool(cursor_written),
    }

def run_harvest_for_workspace(*, workspace_root: Path, core_root: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    core_root = core_root or _repo_root()
    policy = _load_policy(core_root)
    if not policy.enabled:
        return {"status": "SKIPPED", "reason": "POLICY_DISABLED"}

    out_path = (workspace_root / policy.output_path).resolve()
    return harvest_to_path(workspace_root=workspace_root, out_path=out_path, dry_run=bool(dry_run), core_root=core_root)


def action_from_harvest_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    if status not in {"OK", "FAIL", "WOULD_WRITE"}:
        return None

    out = result.get("out")
    out_s = str(out) if isinstance(out, str) else ""
    out_hint = ""
    if out_s:
        try:
            p = Path(out_s)
            parts = [x for x in p.parts if x]
            out_hint = "/".join(parts[-4:]) if parts else p.as_posix()
        except Exception:
            out_hint = out_s
    candidates = result.get("candidates")
    candidates_i = int(candidates) if isinstance(candidates, int) else None
    sanitization = result.get("sanitization") if isinstance(result.get("sanitization"), dict) else {}
    sani_status = sanitization.get("status") if isinstance(sanitization, dict) else None

    resolved = status == "OK" and sani_status in {None, "OK"}
    severity = "WARN" if status in {"OK", "WOULD_WRITE"} and not resolved else ("FAIL" if status == "FAIL" else "INFO")

    seed = "HARVEST_PUBLIC_CANDIDATES|" + status + "|" + out_hint
    action_id = sha256(seed.encode("utf-8")).hexdigest()[:16]
    title = "Public candidates harvest status"
    msg = f"{title}: status={status} candidates={candidates_i} sanitization={sani_status}"

    return {
        "action_id": action_id,
        "severity": severity,
        "kind": "HARVEST_PUBLIC_CANDIDATES",
        "milestone_hint": "M6.5",
        "source": "HARVEST_PUBLIC_CANDIDATES",
        "target_milestone": "M6.5",
        "title": title,
        "details": {"out": out_hint, "candidates": candidates_i, "sanitization_status": sani_status},
        "recommendation": "Keep outputs offline and sanitized; do not include tenant/private markers.",
        "resolved": bool(resolved),
        "message": msg[:300],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.learning.harvest_public_candidates", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", default="false")
    args = ap.parse_args(argv)

    core_root = _repo_root()
    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID", "message": str(workspace_root)}, ensure_ascii=False, sort_keys=True))
        return 2

    try:
        dry_run = _parse_bool(str(args.dry_run))
    except Exception:
        print(json.dumps({"status": "FAIL", "error_code": "INVALID_DRY_RUN"}, ensure_ascii=False, sort_keys=True))
        return 2

    policy = _load_policy(core_root)
    if not policy.enabled:
        print(json.dumps({"status": "OK", "note": "POLICY_DISABLED"}, ensure_ascii=False, sort_keys=True))
        return 0

    out_rel = str(args.out) if args.out is not None else policy.output_path
    out_path = (workspace_root / out_rel).resolve()
    result = harvest_to_path(workspace_root=workspace_root, out_path=out_path, dry_run=dry_run, core_root=core_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"OK", "WOULD_WRITE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
