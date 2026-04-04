"""CI gate + pre-agent bootstrap gate.

Validates context bootstrap tiers (existence + freshness + optional schema).
Phase 1 extension: --gate mode adds health check + profile resolution as
mandatory pre-agent gates with grace mode (first N invocations = WARN).
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIER_1_STATUS: list[tuple[str, str | None]] = [
    (".cache/reports/system_status.v1.json", "schemas/system-status.schema.json"),
    (".cache/reports/portfolio_status.v1.json", None),
    (".cache/roadmap_state.v1.json", None),
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
                check_root = workspace_root
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


# ── Bootstrap Gate (Phase 1 extension) ─────────────────────���────

_GATE_EVIDENCE_PATH = ".cache/reports/bootstrap_evidence.v1.json"
_GRACE_COUNTER_PATH = ".cache/reports/bootstrap_grace_counter.json"
_DEFAULT_GRACE_INVOCATIONS = 2
_MIN_HEALTH_SCORE = 0.8


def _check_health_gate(workspace_root: Path) -> dict[str, Any]:
    """Health score >= 0.8 required. Returns gate result."""
    try:
        from src.benchmark.eval_runner_runtime import _compute_context_health_lens
        health = _compute_context_health_lens(workspace_root, {})
        score = health.get("score", 0.0)
        return {
            "gate": "health",
            "status": "PASS" if score >= _MIN_HEALTH_SCORE else "FAIL",
            "score": round(score, 4),
            "min_required": _MIN_HEALTH_SCORE,
            "reasons": health.get("reasons", []),
        }
    except Exception as exc:
        return {
            "gate": "health",
            "status": "WARN",
            "score": 0.0,
            "min_required": _MIN_HEALTH_SCORE,
            "reasons": [f"health check unavailable: {exc}"],
        }


def _check_profile_gate(workspace_root: Path) -> dict[str, Any]:
    """Profile resolution must succeed."""
    try:
        from src.ops.context_profile_resolver import resolve_profile
        profile = resolve_profile(workspace_root)
        return {
            "gate": "profile",
            "status": "PASS",
            "profile_id": profile.get("profile_id", "UNKNOWN"),
            "resolution_method": profile.get("resolution_method", "unknown"),
        }
    except Exception as exc:
        return {
            "gate": "profile",
            "status": "FAIL",
            "profile_id": "UNKNOWN",
            "resolution_method": "error",
            "reasons": [str(exc)],
        }


def _load_grace_counter(workspace_root: Path) -> int:
    """Load current grace invocation counter."""
    counter_path = workspace_root / _GRACE_COUNTER_PATH
    if counter_path.exists():
        try:
            data = json.loads(counter_path.read_text(encoding="utf-8"))
            return int(data.get("count", 0))
        except Exception:
            pass
    return 0


def _save_grace_counter(workspace_root: Path, count: int) -> None:
    counter_path = workspace_root / _GRACE_COUNTER_PATH
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    counter_path.write_text(json.dumps({"count": count, "updated_at": _now_iso()}), encoding="utf-8")


def run_bootstrap_gate(
    *,
    repo_root: Path,
    workspace_root: Path,
    grace_invocations: int = _DEFAULT_GRACE_INVOCATIONS,
    freshness_threshold: int = DEFAULT_FRESHNESS_THRESHOLD,
) -> dict[str, Any]:
    """Full bootstrap gate: tiers + health + profile.

    Grace mode: first N invocations return WARN instead of BLOCKED.
    After grace period, FAIL results in BLOCKED (exit 1).
    Once PASS is achieved, result is cached for the session.
    """
    # Check cached evidence (session-scoped)
    evidence_path = workspace_root / _GATE_EVIDENCE_PATH
    if evidence_path.exists():
        try:
            cached = json.loads(evidence_path.read_text(encoding="utf-8"))
            if cached.get("gate_result") == "PASS":
                cached["from_cache"] = True
                return cached
        except Exception:
            pass

    # Run tier checks
    tier_result = run_bootstrap_check(
        repo_root=repo_root,
        workspace_root=workspace_root,
        freshness_threshold=freshness_threshold,
    )

    # Run gate checks
    health_gate = _check_health_gate(workspace_root)
    profile_gate = _check_profile_gate(workspace_root)

    gates = [health_gate, profile_gate]
    any_gate_fail = any(g["status"] == "FAIL" for g in gates)
    any_tier_fail = tier_result["status"] == "FAIL"

    # Determine gate result with grace mode
    grace_count = _load_grace_counter(workspace_root)

    if any_gate_fail or any_tier_fail:
        if grace_count < grace_invocations:
            gate_result = "WARN"
            _save_grace_counter(workspace_root, grace_count + 1)
        else:
            gate_result = "BLOCKED"
    else:
        gate_result = "PASS"

    result = {
        "version": "v1",
        "generated_at": _now_iso(),
        "gate_result": gate_result,
        "workspace_root": str(workspace_root),
        "tiers": tier_result["tiers"],
        "tier_status": tier_result["status"],
        "gates": gates,
        "health_score": health_gate.get("score", 0.0),
        "profile_id": profile_gate.get("profile_id", "UNKNOWN"),
        "grace_count": grace_count,
        "grace_limit": grace_invocations,
        "issues": tier_result.get("issues", []),
        "from_cache": False,
    }

    # Write evidence (cache for session)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context bootstrap tier check + gate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--freshness-threshold", type=int, default=DEFAULT_FRESHNESS_THRESHOLD)
    parser.add_argument("--gate", action="store_true", help="Run full bootstrap gate (health + profile + grace)")
    parser.add_argument("--grace-invocations", type=int, default=_DEFAULT_GRACE_INVOCATIONS)
    args = parser.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    ws_raw = str(args.workspace_root or "").strip()
    ws = Path(ws_raw).resolve() if ws_raw else repo

    if args.gate:
        result = run_bootstrap_gate(
            repo_root=repo,
            workspace_root=ws,
            grace_invocations=args.grace_invocations,
            freshness_threshold=args.freshness_threshold,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        gate = result["gate_result"]
        if gate == "BLOCKED":
            return 1
        return 0
    else:
        result = run_bootstrap_check(
            repo_root=repo,
            workspace_root=ws,
            freshness_threshold=args.freshness_threshold,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
