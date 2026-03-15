"""Work intake proximity scoring.

Enriches work item prioritization with code-proximity signals:
1. Recently changed files relevance (hot file overlap)
2. Import graph neighborhood (connected file distance)
3. Active claim overlap (avoid conflicts, prefer locality)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _extract_file_hints(work_item: dict[str, Any]) -> list[str]:
    """Extract file path hints from a work item's metadata."""
    hints: list[str] = []
    for key in ("affected_files", "files", "paths", "scope_files"):
        val = work_item.get(key)
        if isinstance(val, list):
            hints.extend(str(v) for v in val if isinstance(v, str))
        elif isinstance(val, str):
            hints.append(val)

    # Also extract from title/description using path-like patterns
    for key in ("title", "description", "summary"):
        text = str(work_item.get(key) or "")
        # Match patterns like src/ops/foo.py, web/apps/bar.tsx
        found = re.findall(r"(?:[\w.-]+/)+[\w.-]+\.\w+", text)
        hints.extend(found)

    return list(set(hints))


def compute_proximity_score(
    *,
    work_item: dict[str, Any],
    hot_files: list[dict[str, Any]],
    import_graph: dict[str, list[str]],
    active_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute a proximity score for a work item.

    Returns a score dict with:
    - hot_file_score: 0-100 based on overlap with recently changed files
    - neighbor_score: 0-100 based on import graph connectivity
    - claim_overlap_score: 0-100 based on proximity to active claims
    - total_score: weighted combination
    """
    file_hints = _extract_file_hints(work_item)

    # 1. Hot file score
    hot_file_score = 0.0
    if file_hints and hot_files:
        hot_paths = {h["path"] for h in hot_files}
        overlap = sum(1 for f in file_hints if f in hot_paths)
        # Also partial matches (same directory)
        hot_dirs = {"/".join(h["path"].split("/")[:-1]) for h in hot_files if "/" in h["path"]}
        dir_overlap = sum(
            1 for f in file_hints
            if "/" in f and "/".join(f.split("/")[:-1]) in hot_dirs
        )
        hot_file_score = min(100.0, (overlap * 40) + (dir_overlap * 15))

    # 2. Neighbor score via import graph
    neighbor_score = 0.0
    if file_hints and import_graph:
        from src.session.context_enrichment import compute_neighbors
        neighbors = compute_neighbors(
            import_graph=import_graph,
            target_files=file_hints,
            depth=1,
        )
        # Score based on how many graph files the work item touches
        graph_files = set(import_graph.keys())
        hint_in_graph = sum(1 for f in file_hints if f in graph_files)
        neighbor_in_graph = len(set(neighbors) & graph_files)
        neighbor_score = min(100.0, (hint_in_graph * 30) + (neighbor_in_graph * 5))

    # 3. Claim overlap score
    claim_overlap_score = 0.0
    if file_hints and active_claims:
        claim_items = {str(c.get("work_item_id") or "") for c in active_claims}
        wi_id = str(work_item.get("work_item_id") or work_item.get("id") or "")
        # If this exact item is already claimed, penalize
        if wi_id in claim_items:
            claim_overlap_score = -50.0
        else:
            # Check if claimed items share files
            for claim in active_claims:
                claim_files = _extract_file_hints(claim)
                shared = set(file_hints) & set(claim_files)
                if shared:
                    claim_overlap_score += 20.0  # Boost: locality with active work
            claim_overlap_score = min(100.0, claim_overlap_score)

    # Weighted total
    total = (
        hot_file_score * 0.4
        + neighbor_score * 0.35
        + max(0.0, claim_overlap_score) * 0.25
    )

    return {
        "work_item_id": str(work_item.get("work_item_id") or work_item.get("id") or ""),
        "file_hints": file_hints,
        "hot_file_score": round(hot_file_score, 1),
        "neighbor_score": round(neighbor_score, 1),
        "claim_overlap_score": round(claim_overlap_score, 1),
        "total_proximity_score": round(total, 1),
    }


def rank_work_items(
    *,
    work_items: list[dict[str, Any]],
    repo_root: Path,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Rank a list of work items by proximity score.

    Combines existing priority (bucket/severity) with code proximity signals.
    """
    from src.session.context_enrichment import (
        compute_hot_files,
        compute_import_graph,
    )
    from src.ops.work_item_claims import load_claims

    repo_root = repo_root.resolve()
    ws = (workspace_root or repo_root).resolve()

    # Compute signals
    hot_files = compute_hot_files(repo_root=repo_root, days=7, top_n=30)
    import_graph = compute_import_graph(repo_root=repo_root, max_files=300)
    active_claims = load_claims(ws)

    # Score each work item
    scored: list[dict[str, Any]] = []
    for wi in work_items:
        score = compute_proximity_score(
            work_item=wi,
            hot_files=hot_files,
            import_graph=import_graph,
            active_claims=active_claims,
        )

        # Combine with original priority if available
        original_priority = float(wi.get("priority") or wi.get("severity") or 50)
        combined = (original_priority * 0.6) + (score["total_proximity_score"] * 0.4)

        scored.append({
            **score,
            "original_priority": original_priority,
            "combined_score": round(combined, 1),
            "work_item": wi,
        })

    # Sort by combined score descending
    scored.sort(key=lambda x: x["combined_score"], reverse=True)

    return {
        "version": "v1",
        "kind": "work-intake-proximity-ranking",
        "total_items": len(scored),
        "signals": {
            "hot_files_count": len(hot_files),
            "import_graph_files": len(import_graph),
            "active_claims": len(active_claims),
        },
        "ranked_items": scored,
        "status": "OK",
    }
