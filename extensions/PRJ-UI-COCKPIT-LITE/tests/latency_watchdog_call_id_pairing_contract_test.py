from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / ".cache" / "ws_customer_default" / ".cache" / "ops" / "latency_watchdog.v1.py"
    if not script.exists():
        raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: script missing")

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        chat_dir = ws_root / ".cache" / "chat_console"
        reports_dir = ws_root / ".cache" / "reports"
        index_dir = ws_root / ".cache" / "index"
        chat_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        index_dir.mkdir(parents=True, exist_ok=True)

        base = datetime.now(timezone.utc) - timedelta(minutes=3)
        events = [
            {
                "version": "v1",
                "type": "OP_CALL",
                "seq": 1,
                "ts": _iso(base),
                "op": "planner-chat-send-llm",
                "call_id": "call_A",
                "trace_meta": {"run_id": "RUN-1", "call_id": "call_A"},
                "evidence_paths": [],
            },
            {
                "version": "v1",
                "type": "OP_CALL",
                "seq": 2,
                "ts": _iso(base + timedelta(seconds=1)),
                "op": "planner-chat-send-llm",
                "call_id": "call_B",
                "trace_meta": {"run_id": "RUN-1", "call_id": "call_B"},
                "evidence_paths": [],
            },
            {
                "version": "v1",
                "type": "RESULT",
                "seq": 3,
                "ts": _iso(base + timedelta(seconds=2)),
                "op": "planner-chat-send-llm",
                "status": "FAIL",
                "call_id": "call_B",
                "result_for_seq": 2,
                "trace_meta": {"run_id": "RUN-1", "call_id": "call_B"},
                "evidence_paths": [],
            },
        ]
        log_path = chat_dir / "chat_log.v1.jsonl"
        log_path.write_text("\n".join(json.dumps(item, ensure_ascii=True, sort_keys=True) for item in events) + "\n", encoding="utf-8")

        cmd = [
            sys.executable,
            str(script),
            "--workspace-root",
            str(ws_root),
            "--out",
            ".cache/reports/latency_watchdog.v1.json",
            "--window-lines",
            "200",
            "--stuck-seconds",
            "0",
        ]
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: watchdog rc != 0")

        payload_path = reports_dir / "latency_watchdog.v1.json"
        if not payload_path.exists():
            raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: output missing")
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        op_latency = payload.get("op_latency") if isinstance(payload.get("op_latency"), dict) else {}
        pairs = op_latency.get("pairs") if isinstance(op_latency.get("pairs"), dict) else {}
        pairing = pairs.get("pairing_mode_counts") if isinstance(pairs.get("pairing_mode_counts"), dict) else {}
        if int(pairing.get("call_id") or 0) != 1:
            raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: call_id pairing count")
        if int(pairing.get("legacy") or 0) != 0:
            raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: legacy pairing should be 0")

        running = op_latency.get("running_ops_top") if isinstance(op_latency.get("running_ops_top"), list) else []
        if not running:
            raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: running op missing")
        first = running[0] if isinstance(running[0], dict) else {}
        if int(first.get("seq") or 0) != 1:
            raise SystemExit("latency_watchdog_call_id_pairing_contract_test failed: wrong seq paired (call_id-first broken)")


if __name__ == "__main__":
    main()
