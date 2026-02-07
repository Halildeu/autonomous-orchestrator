from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RetentionPolicy:
    evidence_days: int = 7
    dlq_days: int = 14
    cache_days: int = 7


def repo_root() -> Path:
    # src/ops/reaper.py -> ops -> src -> repo root
    return Path(__file__).resolve().parents[2]


def parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError("Expected boolean value true|false.")


def parse_iso8601(value: str) -> datetime:
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_int(value: Any, *, default: int) -> int:
    try:
        n = int(value)
    except Exception:
        return default
    if n < 0:
        return default
    return n


def load_retention_policy(root: Path) -> RetentionPolicy:
    policy_path = root / "policies" / "policy_retention.v1.json"
    if not policy_path.exists():
        return RetentionPolicy()
    try:
        obj = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return RetentionPolicy()
    if not isinstance(obj, dict):
        return RetentionPolicy()
    return RetentionPolicy(
        evidence_days=_safe_int(obj.get("evidence_days"), default=RetentionPolicy.evidence_days),
        dlq_days=_safe_int(obj.get("dlq_days"), default=RetentionPolicy.dlq_days),
        cache_days=_safe_int(obj.get("cache_days"), default=RetentionPolicy.cache_days),
    )


def _dt_from_file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


_DLQ_PREFIX_RE = re.compile(r"^(?P<ymd>\d{8})[-_](?P<hms>\d{6})")


def dlq_file_timestamp(path: Path) -> datetime:
    name = path.name
    m = _DLQ_PREFIX_RE.match(name)
    if m:
        try:
            stamp = m.group("ymd") + m.group("hms")
            return datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except Exception:
            return _dt_from_file_mtime(path)
    return _dt_from_file_mtime(path)


def evidence_run_timestamp(summary_path: Path) -> datetime | None:
    try:
        obj = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    finished_at = obj.get("finished_at") if isinstance(obj.get("finished_at"), str) else ""
    started_at = obj.get("started_at") if isinstance(obj.get("started_at"), str) else ""
    ts = finished_at or started_at
    if not ts:
        return None
    try:
        return parse_iso8601(ts)
    except Exception:
        return None


def _rel_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def compute_reaper_report(*, root: Path, dry_run: bool, now: datetime) -> dict[str, Any]:
    policy = load_retention_policy(root)

    cutoff_evidence = now - timedelta(days=int(policy.evidence_days))
    cutoff_dlq = now - timedelta(days=int(policy.dlq_days))
    cutoff_cache = now - timedelta(days=int(policy.cache_days))

    evidence_candidates: list[Path] = []
    dlq_candidates: list[Path] = []
    cache_candidates: list[Path] = []

    evidence_dir = root / "evidence"
    if evidence_dir.exists():
        for summary_path in sorted(evidence_dir.rglob("summary.json")):
            if summary_path.name != "summary.json":
                continue
            run_dir = summary_path.parent
            ts = evidence_run_timestamp(summary_path)
            if ts is None:
                continue
            if ts < cutoff_evidence:
                evidence_candidates.append(run_dir)

    dlq_dir = root / "dlq"
    if dlq_dir.exists():
        for path in sorted(dlq_dir.glob("*.json")):
            ts = dlq_file_timestamp(path)
            if ts < cutoff_dlq:
                dlq_candidates.append(path)

    cache_dir = root / ".cache"
    if cache_dir.exists():
        for p in sorted(cache_dir.rglob("*")):
            if not p.is_file():
                continue
            ts = _dt_from_file_mtime(p)
            if ts < cutoff_cache:
                cache_candidates.append(p)

    evidence_candidates = sorted({p.resolve() for p in evidence_candidates}, key=lambda p: _rel_path(root, p))

    evidence_deleted = 0
    dlq_deleted = 0
    cache_deleted = 0

    if not dry_run:
        for run_dir in evidence_candidates:
            shutil.rmtree(run_dir)
            evidence_deleted += 1

        for path in dlq_candidates:
            path.unlink()
            dlq_deleted += 1

        for path in cache_candidates:
            path.unlink()
            cache_deleted += 1

        # Best-effort cleanup: remove empty .cache subdirs.
        if cache_dir.exists():
            for p in sorted(cache_dir.rglob("*"), reverse=True):
                if p.is_dir():
                    try:
                        p.rmdir()
                    except OSError:
                        pass

    report = {
        "dry_run": bool(dry_run),
        "now": now.isoformat(),
        "cutoffs": {
            "evidence_cutoff": cutoff_evidence.isoformat(),
            "dlq_cutoff": cutoff_dlq.isoformat(),
            "cache_cutoff": cutoff_cache.isoformat(),
        },
        "evidence": {
            "candidates": len(evidence_candidates),
            "deleted": evidence_deleted,
            "paths": [_rel_path(root, p) for p in evidence_candidates],
        },
        "dlq": {
            "candidates": len(dlq_candidates),
            "deleted": dlq_deleted,
            "paths": [_rel_path(root, p) for p in sorted(dlq_candidates, key=lambda p: _rel_path(root, p))],
        },
        "cache": {
            "candidates": len(cache_candidates),
            "deleted": cache_deleted,
            "paths": [_rel_path(root, p) for p in sorted(cache_candidates, key=lambda p: _rel_path(root, p))],
        },
    }
    return report


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.reaper")
    ap.add_argument("--dry-run", required=True, help="true|false")
    ap.add_argument("--now", help="ISO8601 timestamp (optional).")
    ap.add_argument("--out", required=True, help="Output report JSON path.")
    args = ap.parse_args(argv)

    try:
        dry_run = parse_bool(str(args.dry_run))
    except ValueError as e:
        print(json.dumps({"status": "ERROR", "message": str(e)}, ensure_ascii=False, sort_keys=True))
        return 2

    if args.now:
        try:
            now = parse_iso8601(str(args.now))
        except Exception as e:
            print(
                json.dumps(
                    {"status": "ERROR", "message": "Invalid --now ISO8601 timestamp.", "error": str(e)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 2
    else:
        now = datetime.now(timezone.utc)

    root = repo_root()
    out_path = Path(str(args.out))
    out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()

    report = compute_reaper_report(root=root, dry_run=dry_run, now=now)
    write_report(out_path, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
