"""Write-Ahead Log (WAL) — durable state write foundation.

Provides crash-safe state writes by logging intent before applying.
On recovery, uncommitted WAL entries are replayed to bring state up to date.

Design:
    1. Write intent to WAL (append-only JSONL)
    2. Apply the actual state change (atomic write)
    3. Mark WAL entry as committed
    4. On startup: scan for uncommitted entries → replay

WAL files live in workspace .cache/wal/ — one per store.

Usage::

    from src.shared.wal import WALWriter

    wal = WALWriter(workspace_root=Path(".cache/ws_customer_default"), store_id="work_item_state")

    # Guarded write
    with wal.transaction(target_path, new_data) as txn:
        write_json_atomic(target_path, new_data)
        txn.commit()

    # Recovery (at startup)
    pending = wal.recover()
    for entry in pending:
        write_json_atomic(entry["target_path"], entry["data"])
        wal.mark_committed(entry["wal_id"])
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class WALWriter:
    """Append-only write-ahead log for a single store."""

    def __init__(self, *, workspace_root: Path, store_id: str):
        self._wal_dir = workspace_root / ".cache" / "wal"
        self._wal_dir.mkdir(parents=True, exist_ok=True)
        self._wal_path = self._wal_dir / f"{store_id}.wal.jsonl"
        self._store_id = store_id

    def _append(self, entry: dict[str, Any]) -> None:
        """Append a single entry to WAL (fsync'd)."""
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        with self._wal_path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def _read_entries(self) -> list[dict[str, Any]]:
        """Read all WAL entries."""
        if not self._wal_path.exists():
            return []
        entries = []
        for line in self._wal_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    @contextmanager
    def transaction(self, target_path: Path, data: Any) -> Generator[_WALTransaction, None, None]:
        """Context manager for a WAL-guarded write.

        Writes intent to WAL before yielding. Caller performs the actual write,
        then calls txn.commit(). If commit() is never called (crash), the entry
        remains uncommitted for recovery.
        """
        wal_id = f"wal-{uuid.uuid4().hex[:12]}"
        entry = {
            "wal_id": wal_id,
            "store_id": self._store_id,
            "target_path": str(target_path),
            "data": data,
            "status": "PENDING",
            "created_at": _now_iso(),
        }
        self._append(entry)
        logger.debug("WAL PENDING store=%s wal_id=%s target=%s", self._store_id, wal_id, target_path)

        txn = _WALTransaction(wal=self, wal_id=wal_id)
        try:
            yield txn
        except Exception:
            # Write failed — entry stays PENDING for recovery
            raise

    def mark_committed(self, wal_id: str) -> None:
        """Mark a WAL entry as committed (append COMMITTED record)."""
        self._append({
            "wal_id": wal_id,
            "store_id": self._store_id,
            "status": "COMMITTED",
            "committed_at": _now_iso(),
        })
        logger.debug("WAL COMMITTED store=%s wal_id=%s", self._store_id, wal_id)

    def recover(self) -> list[dict[str, Any]]:
        """Find uncommitted WAL entries for replay.

        Returns entries where status=PENDING and no corresponding COMMITTED record exists.
        """
        entries = self._read_entries()
        committed_ids: set[str] = set()
        pending: dict[str, dict[str, Any]] = {}

        for e in entries:
            wid = e.get("wal_id", "")
            status = e.get("status", "")
            if status == "COMMITTED":
                committed_ids.add(wid)
            elif status == "PENDING" and "data" in e:
                pending[wid] = e

        # Return only truly uncommitted entries
        uncommitted = [
            e for wid, e in pending.items()
            if wid not in committed_ids
        ]

        if uncommitted:
            logger.warning(
                "WAL RECOVERY store=%s uncommitted=%d entries",
                self._store_id, len(uncommitted),
            )

        return uncommitted

    def truncate(self) -> int:
        """Remove all committed entries from WAL to reclaim space.

        Keeps only uncommitted (PENDING without COMMITTED) entries.
        Returns number of entries removed.
        """
        entries = self._read_entries()
        committed_ids: set[str] = set()

        for e in entries:
            if e.get("status") == "COMMITTED":
                committed_ids.add(e.get("wal_id", ""))

        # Keep only PENDING entries without COMMITTED counterpart
        kept = [
            e for e in entries
            if not (e.get("status") == "COMMITTED") and not (
                e.get("status") == "PENDING" and e.get("wal_id", "") in committed_ids
            )
        ]

        removed = len(entries) - len(kept)

        if removed > 0:
            # Rewrite WAL with only uncommitted entries
            tmp = self._wal_path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                for e in kept:
                    f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
            tmp.replace(self._wal_path)
            logger.info("WAL TRUNCATE store=%s removed=%d kept=%d", self._store_id, removed, len(kept))

        return removed


class _WALTransaction:
    """Transaction handle returned by WALWriter.transaction()."""

    def __init__(self, wal: WALWriter, wal_id: str):
        self._wal = wal
        self._wal_id = wal_id
        self._committed = False

    def commit(self) -> None:
        """Mark this transaction as committed."""
        if not self._committed:
            self._wal.mark_committed(self._wal_id)
            self._committed = True

    @property
    def committed(self) -> bool:
        return self._committed
