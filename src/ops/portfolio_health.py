"""Portfolio health aggregation across managed repos.

Computes aggregate health score from individual repo context health scores.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def compute_portfolio_health(
    *,
    orchestrator_workspace: Path,
    managed_repos: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate health scores across all managed repos.

    Args:
        orchestrator_workspace: Orchestrator workspace root
        managed_repos: List of {repo_id, repo_root, workspace_root} dicts

    Returns:
        Portfolio health report with per-repo scores and aggregate.
    """
    from src.benchmark.eval_runner_runtime import _compute_context_health_lens

    repos: list[dict[str, Any]] = []
    total_score = 0.0
    worst_component = ""
    worst_component_score = 100.0

    for repo in managed_repos:
        repo_id = str(repo.get("repo_id") or repo.get("repo_slug") or "unknown")
        ws_root = repo.get("workspace_root")
        if not ws_root:
            repos.append({"repo_id": repo_id, "score": 0, "grade": "F", "status": "SKIP", "reason": "no_workspace"})
            continue

        ws_path = Path(str(ws_root))
        if not ws_path.exists():
            repos.append({"repo_id": repo_id, "score": 0, "grade": "F", "status": "SKIP", "reason": "workspace_missing"})
            continue

        health = _compute_context_health_lens(workspace_root=ws_path, lenses_policy={})
        score_100 = int(float(health.get("score", 0)) * 100)
        repos.append({
            "repo_id": repo_id,
            "score": score_100,
            "grade": _grade(score_100),
            "status": health.get("status", "UNKNOWN"),
            "components": health.get("components", {}),
            "reasons": health.get("reasons", []),
        })
        total_score += score_100

        # Track worst component across all repos
        for comp_name, comp_data in health.get("components", {}).items():
            comp_score = float(comp_data.get("score", 0))
            comp_max = float(comp_data.get("max", 20))
            normalized = (comp_score / comp_max * 100) if comp_max > 0 else 0
            if normalized < worst_component_score:
                worst_component_score = normalized
                worst_component = comp_name

    portfolio_score = int(total_score / len(repos)) if repos else 0

    report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "portfolio_score": portfolio_score,
        "portfolio_grade": _grade(portfolio_score),
        "repo_count": len(repos),
        "repos": repos,
        "worst_component": worst_component,
        "worst_component_score": int(worst_component_score),
    }

    # Write portfolio health report
    out_path = orchestrator_workspace / ".cache" / "reports" / "portfolio_context_health.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return report
