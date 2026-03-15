"""CI gate: validate context bootstrap tiers (existence + freshness + optional schema)."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIER_1_STATUS: list[tuple[str, str | None]] = [
    (".cache/ws_customer_default/.cache/reports/system_status.v1.json", "schemas/system-status.schema.json"),
    (".cache/ws_customer_default/.cache/reports/portfolio_status.v1.json", None),
    (".cache/ws_customer_default/.cache/roadmap_state.v1.json", None),
]

TIER_2_STRUCTURAL: list[tuple[str, str | None]] = [
    ("AGENTS.md", None),
    ("docs/OPERATIONS/CODEX-UX.md", None),
    ("docs/LAYER-MODEL-LOCK.v1.md", None),
]

TIER_3_PROJECT: list[tuple[str, str | None]] = [
    ("roadmaps/SSOT/roadmap.v1.json", "schemas/roadmap.schema.json"),
]

DEFAULT_FRESHNESS_THRESHOLD = 86400  # 24 hours


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check_file(
    root: Path,
    rel_path: str,
    schema_rel: str | None,
    threshold: int,
) -> dict[str, Any]:
    full = root / rel_path
    entry: dict[str, Any] = {"path": rel_path, "exists": False, "issues": []}

    if not full.exists():
        entry["issues"].append("MISSING")
        return entry

    entry["exists"] = True

    # Freshness
    try:
        mtime = full.stat().st_mtime
        age = int(time.time() - mtime)
        entry["age_seconds"] = age
        entry["fresh"] = age <= threshold
        if not entry["fresh"]:
            entry["issues"].append(f"STALE (age={age}s > threshold={threshold}s)")
    except Exception:
        entry["fresh"] = False
        entry["issues"].append("STAT_ERROR")

    # Schema validation (optional)
    if schema_rel:
        schema_path = root / schema_rel
        if schema_path.exists():
            try:
                from jsonschema import Draft202012Validator

                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                data = json.loads(full.read_text(encoding="utf-8"))
                validator = Draft202012Validator(schema)
                errs = list(validator.iter_errors(data))
                entry["schema_valid"] = len(errs) == 0
                if errs:
                    entry["issues"].append(f"SCHEMA_ERRORS ({len(errs)})")
            except Exception as exc:
                entry["schema_valid"] = False
                entry["issues"].append(f"VALIDATION_ERROR: {exc}")
        else:
            entry["schema_valid"] = True  # Schema not found, skip

    return entry


def run_bootstrap_check(
    *,
    repo_root: Path,
    workspace_root: Path,
    freshness_threshold: int = DEFAULT_FRESHNESS_THRESHOLD,
) -> dict[str, Any]:
    """Run bootstrap validation on all 3 tiers. Returns structured report."""
    tiers_config = [
        (1, "status_context", TIER_1_STATUS),
        (2, "structural_context", TIER_2_STRUCTURAL),
        (3, "project_context", TIER_3_PROJECT),
    ]

    tiers: list[dict[str, Any]] = []
    all_issues: list[str] = []
    any_fail = False

    for tier_num, tier_name, file_list in tiers_config:
        files: list[dict[str, Any]] = []
        tier_status = "OK"

        for rel_path, schema_rel in file_list:
            # Tier 1 files are workspace-relative, Tier 2-3 are repo-relative
            if rel_path.startswith(".cache/"):
                check_root = repo_root
            else:
                check_root = repo_root

            entry = _check_file(check_root, rel_path, schema_rel, freshness_threshold)
            files.append(entry)

            if entry.get("issues"):
                for issue in entry["issues"]:
                    all_issues.append(f"tier{tier_num}:{rel_path}: {issue}")
                if not entry["exists"]:
                    if tier_num <= 2:
                        tier_status = "FAIL"
                    else:
                        tier_status = "WARN" if tier_status == "OK" else tier_status
                elif not entry.get("fresh", True):
                    tier_status = "WARN" if tier_status == "OK" else tier_status

        if tier_status == "FAIL":
            any_fail = True

        tiers.append({
            "tier": tier_num,
            "name": tier_name,
            "files": files,
            "status": tier_status,
        })

    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "tiers": tiers,
        "status": "FAIL" if any_fail else "OK",
        "issues": all_issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context bootstrap tier check")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--freshness-threshold", type=int, default=DEFAULT_FRESHNESS_THRESHOLD)
    args = parser.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    ws_raw = str(args.workspace_root or "").strip()
    ws = Path(ws_raw).resolve() if ws_raw else repo

    result = run_bootstrap_check(
        repo_root=repo,
        workspace_root=ws,
        freshness_threshold=args.freshness_threshold,
    )

    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
