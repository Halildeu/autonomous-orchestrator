from __future__ import annotations

import importlib.util
import json
import tempfile
import urllib.request
from pathlib import Path


def _load_utils(repo_root: Path):
    utils_path = repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "tests" / "test_utils.py"
    spec = importlib.util.spec_from_file_location("ui_cockpit_test_utils", utils_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_id(item: dict) -> str:
    direct = item.get("call_id")
    if isinstance(direct, str) and direct:
        return direct
    trace = item.get("trace_meta") if isinstance(item.get("trace_meta"), dict) else {}
    traced = trace.get("call_id")
    return str(traced) if isinstance(traced, str) else ""


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    utils = _load_utils(repo_root)
    repo_root = utils.find_repo_root(Path(__file__).resolve())

    with tempfile.TemporaryDirectory() as tmp:
        ws = utils.make_workspace(Path(tmp))
        server, port = utils.start_server(repo_root, ws)
        try:
            base = f"http://127.0.0.1:{port}"
            payload = {
                "op": "planner-chat-send-llm",
                "confirm": True,
                "args": {
                    "thread": "alpha",
                    "title": "Test",
                    "body": "Call id and result_for_seq contract",
                    "provider_id": "invalid-provider",
                    "model": "dummy-model",
                },
            }
            out = _post(base + "/api/op", payload)
            if str(out.get("op") or "") != "planner-chat-send-llm":
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: op mismatch")

            chat = _get(base + "/api/chat?limit=200")
            items = chat.get("items") if isinstance(chat.get("items"), list) else []
            calls = [
                item
                for item in items
                if isinstance(item, dict) and item.get("type") == "OP_CALL" and item.get("op") == "planner-chat-send-llm"
            ]
            results = [
                item
                for item in items
                if isinstance(item, dict) and item.get("type") == "RESULT" and item.get("op") == "planner-chat-send-llm"
            ]
            if not calls:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: OP_CALL missing")
            if not results:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: RESULT missing")

            last_call = calls[-1]
            call_seq = int(last_call.get("seq") or 0)
            if call_seq <= 0:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: OP_CALL seq missing")
            call_id = _call_id(last_call)
            if not call_id:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: OP_CALL call_id missing")

            seq_results = [row for row in results if int(row.get("result_for_seq") or 0) == call_seq]
            if len(seq_results) != 1:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: RESULT(result_for_seq) cardinality != 1")
            result_row = seq_results[0]
            result_call_id = _call_id(result_row)
            if result_call_id != call_id:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: RESULT call_id mismatch")

            terminal_status = str(result_row.get("status") or "").upper()
            if terminal_status not in {"OK", "FAIL", "CANCELLED", "TIMEOUT"}:
                raise SystemExit("planner_chat_send_llm_result_contract_test failed: terminal status invalid")
        finally:
            utils.stop_server(server)


if __name__ == "__main__":
    main()
