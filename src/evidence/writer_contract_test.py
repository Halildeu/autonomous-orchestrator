from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.evidence.writer import EvidenceWriter


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="writer-contract-") as td:
        out_dir = Path(td) / "evidence"
        writer = EvidenceWriter(out_dir=out_dir, run_id="RUN-TEST")

        writer.write_node_log("NODE_X", "first message")
        writer.write_node_log("NODE_X", "second message")

        node_dir = out_dir / "RUN-TEST" / "nodes" / "NODE_X"
        logs_path = node_dir / "logs.txt"
        events_path = node_dir / "events.v1.jsonl"

        logs_text = logs_path.read_text(encoding="utf-8")
        if logs_text != "first message\nsecond message\n":
            raise SystemExit("writer_contract_test failed: logs.txt must append messages in order")

        lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) != 2:
            raise SystemExit("writer_contract_test failed: events.v1.jsonl must contain one line per log call")

        events = [json.loads(line) for line in lines]
        if any(not isinstance(event, dict) for event in events):
            raise SystemExit("writer_contract_test failed: events.v1.jsonl lines must be JSON objects")

        first = events[0]
        second = events[1]
        if first.get("event_type") != "NODE_LOG" or second.get("event_type") != "NODE_LOG":
            raise SystemExit("writer_contract_test failed: event_type must be NODE_LOG")
        if first.get("message") != "first message" or second.get("message") != "second message":
            raise SystemExit("writer_contract_test failed: event messages mismatch")
        if first.get("node_id") != "NODE_X" or second.get("node_id") != "NODE_X":
            raise SystemExit("writer_contract_test failed: node_id mismatch")
        if first.get("run_id") != "RUN-TEST" or second.get("run_id") != "RUN-TEST":
            raise SystemExit("writer_contract_test failed: run_id mismatch")

    print("writer_contract_test: PASS")


if __name__ == "__main__":
    main()
