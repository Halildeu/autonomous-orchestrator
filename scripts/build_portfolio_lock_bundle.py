#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _safe_status(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"OK", "WARN", "FAIL", "UNVERIFIED", "UNKNOWN"}:
        return raw
    return "UNKNOWN"


def _parse_iso_utc(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot",
        action="append",
        default=[],
        help="Snapshot path (repeatable). Defaults to *_post_merge_lock_snapshot.v1.json in evidence dir.",
    )
    parser.add_argument(
        "--evidence-dir",
        default=".cache/reports/release-evidence",
        help="Evidence directory used for default snapshot discovery.",
    )
    parser.add_argument(
        "--glob",
        default="*_post_merge_lock_snapshot.v1.json",
        help="Glob pattern for default discovery under evidence dir.",
    )
    parser.add_argument(
        "--out",
        default=".cache/reports/release-evidence/portfolio_lock_bundle.v1.json",
        help="Output bundle JSON path.",
    )
    return parser.parse_args(argv)


def _resolve_snapshots(args: argparse.Namespace) -> list[Path]:
    explicit: list[Path] = []
    for raw in args.snapshot:
        text = str(raw).strip()
        if not text:
            continue
        p = Path(text).expanduser()
        explicit.append(p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve())
    if explicit:
        return sorted(set(explicit))

    evidence_dir = Path(str(args.evidence_dir).strip() or ".cache/reports/release-evidence").expanduser()
    if not evidence_dir.is_absolute():
        evidence_dir = (Path.cwd() / evidence_dir).resolve()
    pattern = str(args.glob or "*_post_merge_lock_snapshot.v1.json")
    return sorted({p.resolve() for p in evidence_dir.glob(pattern) if p.is_file()})


def _repo_row(snapshot_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    solo = payload.get("solo_policy") if isinstance(payload.get("solo_policy"), dict) else {}
    branch = payload.get("branch_protection") if isinstance(payload.get("branch_protection"), dict) else {}
    pr = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
    workspace_verify = (
        payload.get("workspace_verify") if isinstance(payload.get("workspace_verify"), dict) else {}
    )

    return {
        "repo": str(payload.get("repo") or ""),
        "snapshot_path": str(snapshot_path),
        "snapshot_generated_at": str(payload.get("generated_at") or ""),
        "pull_request": {
            "number": pr.get("number"),
            "url": str(pr.get("url") or ""),
            "state": str(pr.get("state") or ""),
            "merged_at": str(pr.get("merged_at") or ""),
            "merge_commit": str(pr.get("merge_commit") or ""),
        },
        "status": _safe_status(summary.get("status")),
        "all_required_green": bool(summary.get("all_required_green")),
        "failed_check_count": int(summary.get("failed_check_count") or 0),
        "required_checks_missing_count": int(summary.get("required_checks_missing_count") or 0),
        "required_checks_total": int(summary.get("required_checks_total") or 0),
        "solo_policy_status": _safe_status(solo.get("status")),
        "solo_policy_rule": str(solo.get("rule") or ""),
        "solo_policy_violations": [
            str(item) for item in (solo.get("violations") if isinstance(solo.get("violations"), list) else [])
        ],
        "branch_strict": branch.get("strict"),
        "branch_enforce_admins": branch.get("enforce_admins"),
        "branch_required_approving_review_count": branch.get("required_approving_review_count"),
        "branch_require_code_owner_reviews": branch.get("require_code_owner_reviews"),
        "workspace_verify": {
            "system_overall_status": str(workspace_verify.get("system_overall_status") or ""),
            "portfolio_status": str(workspace_verify.get("portfolio_status") or ""),
        },
    }


def _overall_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "IDLE"
    if any(str(row.get("status")) == "FAIL" for row in rows):
        return "FAIL"
    if any(
        str(row.get("status")) in {"WARN", "UNVERIFIED", "UNKNOWN"}
        or str(row.get("solo_policy_status")) in {"FAIL", "WARN", "UNVERIFIED", "UNKNOWN"}
        for row in rows
    ):
        return "WARN"
    return "OK"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    repo = str(row.get("repo") or "").strip().lower()
    pr = row.get("pull_request")
    if not isinstance(pr, dict):
        pr = {}
    pr_number = str(pr.get("number") or "").strip()
    merge_commit = str(pr.get("merge_commit") or "").strip().lower()
    return (repo, pr_number, merge_commit)


def _row_rank(row: dict[str, Any]) -> tuple[datetime, str]:
    ts = _parse_iso_utc(row.get("snapshot_generated_at")) or datetime.fromtimestamp(0, tz=timezone.utc)
    return (ts, str(row.get("snapshot_path") or ""))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    snapshots = _resolve_snapshots(args)
    if not snapshots:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "SNAPSHOT_REQUIRED",
                    "message": "No snapshot files found.",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    rows: list[dict[str, Any]] = []
    load_errors: list[str] = []
    for path in snapshots:
        try:
            obj = _load_json(path)
        except Exception as exc:
            load_errors.append(f"{path}:{exc}")
            continue
        rows.append(_repo_row(path, obj))

    dedup_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicate_source_paths: list[str] = []
    for row in rows:
        key = _row_key(row)
        prev = dedup_map.get(key)
        if prev is None:
            dedup_map[key] = row
            continue
        if _row_rank(row) >= _row_rank(prev):
            duplicate_source_paths.append(str(prev.get("snapshot_path") or ""))
            dedup_map[key] = row
        else:
            duplicate_source_paths.append(str(row.get("snapshot_path") or ""))

    rows = sorted(
        dedup_map.values(),
        key=lambda item: (
            str(item.get("repo") or "").lower(),
            str((item.get("pull_request") or {}).get("number") or ""),
            str((item.get("pull_request") or {}).get("merge_commit") or "").lower(),
        ),
    )

    status = _overall_status(rows)
    if load_errors and status == "OK":
        status = "WARN"

    bundle = {
        "version": "v1",
        "kind": "portfolio-lock-bundle",
        "generated_at": _now_iso_utc(),
        "status": status,
        "summary": {
            "repos_count": len(rows),
            "ok_count": sum(1 for row in rows if str(row.get("status")) == "OK"),
            "warn_count": sum(1 for row in rows if str(row.get("status")) == "WARN"),
            "fail_count": sum(1 for row in rows if str(row.get("status")) == "FAIL"),
            "solo_policy_fail_count": sum(
                1 for row in rows if str(row.get("solo_policy_status")) == "FAIL"
            ),
            "required_checks_missing_total": sum(
                int(row.get("required_checks_missing_count") or 0) for row in rows
            ),
            "failed_check_total": sum(int(row.get("failed_check_count") or 0) for row in rows),
            "load_error_count": len(load_errors),
            "deduped_snapshot_count": len(duplicate_source_paths),
        },
        "sources": [str(path) for path in snapshots],
        "deduped_sources": sorted(set(path for path in duplicate_source_paths if path)),
        "repos": rows,
        "errors": load_errors,
    }

    out_path = Path(str(args.out).strip() or ".cache/reports/release-evidence/portfolio_lock_bundle.v1.json")
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "repos_count": len(rows),
                "load_error_count": len(load_errors),
                "out": str(out_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
