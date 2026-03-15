"""Contract tests for work intake proximity scoring."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_extract_file_hints_from_affected_files() -> None:
    from src.ops.work_intake_proximity import _extract_file_hints
    wi = {"affected_files": ["src/ops/manage.py", "ci/check_standards_lock.py"]}
    hints = _extract_file_hints(wi)
    assert "src/ops/manage.py" in hints
    assert "ci/check_standards_lock.py" in hints


def test_extract_file_hints_from_description() -> None:
    from src.ops.work_intake_proximity import _extract_file_hints
    wi = {"description": "Fix bug in src/session/context_store.py related to TTL"}
    hints = _extract_file_hints(wi)
    assert "src/session/context_store.py" in hints


def test_proximity_score_returns_structure() -> None:
    from src.ops.work_intake_proximity import compute_proximity_score
    wi = {"id": "WI-001", "affected_files": ["src/ops/manage.py"]}
    score = compute_proximity_score(
        work_item=wi,
        hot_files=[{"path": "src/ops/manage.py", "change_count": 5}],
        import_graph={},
        active_claims=[],
    )
    assert "hot_file_score" in score
    assert "neighbor_score" in score
    assert "claim_overlap_score" in score
    assert "total_proximity_score" in score
    assert score["total_proximity_score"] >= 0


def test_hot_file_overlap_boosts_score() -> None:
    from src.ops.work_intake_proximity import compute_proximity_score
    wi = {"affected_files": ["src/ops/manage.py"]}
    score_with = compute_proximity_score(
        work_item=wi,
        hot_files=[{"path": "src/ops/manage.py", "change_count": 5}],
        import_graph={},
        active_claims=[],
    )
    score_without = compute_proximity_score(
        work_item=wi,
        hot_files=[{"path": "completely/unrelated.py", "change_count": 5}],
        import_graph={},
        active_claims=[],
    )
    assert score_with["hot_file_score"] > score_without["hot_file_score"]


def test_already_claimed_penalizes() -> None:
    from src.ops.work_intake_proximity import compute_proximity_score
    wi = {"work_item_id": "WI-001", "affected_files": ["a.py"]}
    score = compute_proximity_score(
        work_item=wi,
        hot_files=[],
        import_graph={},
        active_claims=[{"work_item_id": "WI-001"}],
    )
    assert score["claim_overlap_score"] < 0


def test_rank_work_items_returns_sorted() -> None:
    from src.ops.work_intake_proximity import rank_work_items

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        items = [
            {"id": "WI-001", "priority": 80, "affected_files": ["src/ops/manage.py"]},
            {"id": "WI-002", "priority": 30, "affected_files": ["unknown/file.txt"]},
            {"id": "WI-003", "priority": 50},
        ]
        result = rank_work_items(
            work_items=items,
            repo_root=REPO_ROOT,
            workspace_root=ws,
        )
        assert result["status"] == "OK"
        assert result["total_items"] == 3
        assert len(result["ranked_items"]) == 3
        # First item should have highest combined score
        scores = [r["combined_score"] for r in result["ranked_items"]]
        assert scores == sorted(scores, reverse=True)


def test_rank_empty_list() -> None:
    from src.ops.work_intake_proximity import rank_work_items
    with tempfile.TemporaryDirectory() as tmp:
        result = rank_work_items(
            work_items=[],
            repo_root=REPO_ROOT,
            workspace_root=Path(tmp),
        )
        assert result["status"] == "OK"
        assert result["total_items"] == 0


def test_dir_proximity_boosts() -> None:
    from src.ops.work_intake_proximity import compute_proximity_score
    wi = {"affected_files": ["src/ops/something_new.py"]}
    score = compute_proximity_score(
        work_item=wi,
        hot_files=[{"path": "src/ops/manage.py", "change_count": 5}],
        import_graph={},
        active_claims=[],
    )
    # Same directory should give some boost
    assert score["hot_file_score"] > 0
