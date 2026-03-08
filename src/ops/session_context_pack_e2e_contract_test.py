from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _parse_last_json(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("no-json-object")


def _run_manage(repo_root: Path, args: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "src.ops.manage", *args]
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
    if proc.returncode != 0:
        tail = (proc.stdout or "").strip().splitlines()[-1:] + (proc.stderr or "").strip().splitlines()[-1:]
        raise SystemExit(f"session_context_pack_e2e_contract_test failed: rc={proc.returncode} cmd={args} tail={tail}")
    try:
        return _parse_last_json(proc.stdout)
    except Exception:
        raise SystemExit("session_context_pack_e2e_contract_test failed: json output missing")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.session.cross_session_context import build_cross_session_context

    with tempfile.TemporaryDirectory() as temp_dir:
        ws = Path(temp_dir).resolve()

        session_id = "agent-codex"
        key = "routing_override"
        value = {"bucket": "PROJECT", "reason": "e2e"}

        init_res = _run_manage(
            repo_root,
            [
                "session-init",
                "--workspace-root",
                str(ws),
                "--session-id",
                session_id,
                "--ttl-seconds",
                "3600",
            ],
        )
        if init_res.get("status") != "OK":
            raise SystemExit("session_context_pack_e2e_contract_test failed: session-init status")

        set_res = _run_manage(
            repo_root,
            [
                "session-set",
                "--workspace-root",
                str(ws),
                "--session-id",
                session_id,
                "--key",
                key,
                "--value-json",
                json.dumps(value, ensure_ascii=True, sort_keys=True),
                "--decision-ttl-seconds",
                "600",
            ],
        )
        if set_res.get("status") != "OK":
            raise SystemExit("session_context_pack_e2e_contract_test failed: session-set status")

        cross_res = build_cross_session_context(workspace_root=ws)
        if cross_res.get("status") != "OK":
            raise SystemExit("session_context_pack_e2e_contract_test failed: cross-session status")
        if int(cross_res.get("shared_keys_total") or 0) < 1:
            raise SystemExit("session_context_pack_e2e_contract_test failed: shared_keys_total")
        report_rel = str(cross_res.get("report_path") or "")
        if not report_rel:
            raise SystemExit("session_context_pack_e2e_contract_test failed: cross report path")
        cross_path = (ws / report_rel).resolve()
        if not cross_path.exists():
            raise SystemExit("session_context_pack_e2e_contract_test failed: cross report missing")
        cross_obj = json.loads(cross_path.read_text(encoding="utf-8"))
        shared = cross_obj.get("shared_decisions") if isinstance(cross_obj.get("shared_decisions"), list) else []
        matched = [d for d in shared if isinstance(d, dict) and str(d.get("key") or "") == key]
        if not matched:
            raise SystemExit("session_context_pack_e2e_contract_test failed: shared decision key missing")

        submit_res = _run_manage(
            repo_root,
            [
                "manual-request-submit",
                "--workspace-root",
                str(ws),
                "--text",
                "Session context E2E request",
                "--artifact-type",
                "task",
                "--domain",
                "ops",
                "--kind",
                "feature",
            ],
        )
        if submit_res.get("status") != "OK":
            raise SystemExit("session_context_pack_e2e_contract_test failed: manual-request-submit status")
        request_id = str(submit_res.get("request_id") or "")
        if not request_id:
            raise SystemExit("session_context_pack_e2e_contract_test failed: request_id missing")

        build_res = _run_manage(
            repo_root,
            [
                "context-pack-build",
                "--workspace-root",
                str(ws),
                "--request-id",
                request_id,
                "--mode",
                "detail",
            ],
        )
        if build_res.get("status") != "OK":
            raise SystemExit("session_context_pack_e2e_contract_test failed: context-pack-build status")
        pack_rel = str(build_res.get("context_pack_path") or "")
        if not pack_rel:
            raise SystemExit("session_context_pack_e2e_contract_test failed: context_pack_path missing")
        pack_path = (ws / pack_rel).resolve()
        if not pack_path.exists():
            raise SystemExit("session_context_pack_e2e_contract_test failed: context pack missing")
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        active_pack_path = ws / ".cache" / "index" / "context_pack.v1.json"
        if not active_pack_path.exists():
            raise SystemExit("session_context_pack_e2e_contract_test failed: active context pack missing")
        active_pack = json.loads(active_pack_path.read_text(encoding="utf-8"))
        if str(active_pack.get("context_pack_id") or "") != str(pack.get("context_pack_id") or ""):
            raise SystemExit("session_context_pack_e2e_contract_test failed: active context pack mismatch")

        notes = pack.get("notes") if isinstance(pack.get("notes"), list) else []
        shared_notes = [n for n in notes if isinstance(n, str) and n.startswith("session_shared_keys=")]
        if not shared_notes:
            raise SystemExit("session_context_pack_e2e_contract_test failed: session_shared_keys note missing")
        try:
            shared_count = int(str(shared_notes[-1]).split("=", 1)[1])
        except Exception:
            raise SystemExit("session_context_pack_e2e_contract_test failed: session_shared_keys parse")
        if shared_count < 1:
            raise SystemExit("session_context_pack_e2e_contract_test failed: session_shared_keys must be >=1")

        define = pack.get("define") if isinstance(pack.get("define"), dict) else {}
        decision_refs = define.get("decision_refs") if isinstance(define.get("decision_refs"), list) else []
        has_cross_ref = False
        for ref in decision_refs:
            if not isinstance(ref, dict):
                continue
            if str(ref.get("label") or "") != "session_cross_context":
                continue
            if str(ref.get("path") or "") != report_rel:
                continue
            if str(ref.get("scope") or "") != "workspace":
                continue
            has_cross_ref = True
            break
        if not has_cross_ref:
            raise SystemExit("session_context_pack_e2e_contract_test failed: cross-session decision ref missing")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
