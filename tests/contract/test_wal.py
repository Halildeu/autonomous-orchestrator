"""Contract tests for the WAL (Write-Ahead Log) module."""
from __future__ import annotations

import json
from pathlib import Path

from src.shared.wal import WALWriter
from src.shared.utils import write_json_atomic


def test_wal_transaction_commit(tmp_path: Path):
    """Committed transaction leaves no pending entries."""
    wal = WALWriter(workspace_root=tmp_path, store_id="test")
    target = tmp_path / "state.json"
    data = {"key": "value"}

    with wal.transaction(target, data) as txn:
        write_json_atomic(target, data)
        txn.commit()

    assert txn.committed
    assert target.exists()
    assert json.loads(target.read_text()) == data
    assert wal.recover() == []  # no pending entries


def test_wal_recovery_on_uncommitted(tmp_path: Path):
    """Uncommitted transaction is recoverable."""
    wal = WALWriter(workspace_root=tmp_path, store_id="test")
    target = tmp_path / "state.json"
    data = {"key": "crash_value"}

    # Simulate crash: write WAL entry but don't commit
    wal._append({
        "wal_id": "wal-test-crash",
        "store_id": "test",
        "target_path": str(target),
        "data": data,
        "status": "PENDING",
        "created_at": "2026-01-01T00:00:00Z",
    })

    pending = wal.recover()
    assert len(pending) == 1
    assert pending[0]["wal_id"] == "wal-test-crash"
    assert pending[0]["data"] == data

    # Replay
    write_json_atomic(Path(pending[0]["target_path"]), pending[0]["data"])
    wal.mark_committed("wal-test-crash")

    assert wal.recover() == []
    assert json.loads(target.read_text()) == data


def test_wal_truncate(tmp_path: Path):
    """Truncate removes committed entries."""
    wal = WALWriter(workspace_root=tmp_path, store_id="test")
    target = tmp_path / "state.json"

    # Write 3 committed transactions
    for i in range(3):
        with wal.transaction(target, {"i": i}) as txn:
            write_json_atomic(target, {"i": i})
            txn.commit()

    removed = wal.truncate()
    assert removed == 6  # 3 PENDING + 3 COMMITTED entries removed
    assert wal.recover() == []


def test_wal_multiple_stores(tmp_path: Path):
    """Different stores have independent WAL files."""
    wal_a = WALWriter(workspace_root=tmp_path, store_id="store_a")
    wal_b = WALWriter(workspace_root=tmp_path, store_id="store_b")

    target_a = tmp_path / "a.json"
    target_b = tmp_path / "b.json"

    with wal_a.transaction(target_a, {"store": "a"}) as txn:
        write_json_atomic(target_a, {"store": "a"})
        txn.commit()

    # Only write to WAL but don't commit (simulate crash)
    wal_b._append({
        "wal_id": "wal-b-pending",
        "store_id": "store_b",
        "target_path": str(target_b),
        "data": {"store": "b"},
        "status": "PENDING",
        "created_at": "2026-01-01T00:00:00Z",
    })

    assert wal_a.recover() == []  # a is clean
    assert len(wal_b.recover()) == 1  # b has pending
