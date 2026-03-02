from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"adapter_llm_actions_refactor_contract_test failed: {message}")


def _build_response(**kwargs):
    return dict(kwargs)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.prj_kernel_api.adapter_llm_actions import maybe_handle_llm_actions

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        ws.mkdir(parents=True, exist_ok=True)

        unknown = maybe_handle_llm_actions(
            action="unknown_action",
            params={},
            workspace_root=str(ws),
            repo_root=repo_root,
            env_mode="dotenv",
            request_id="req-unknown",
            auth_checked=True,
            rate_limited=False,
            policy={},
            build_response=_build_response,
        )
        _must(unknown is None, "unknown action must return None")

        init_resp = maybe_handle_llm_actions(
            action="llm_providers_init",
            params={},
            workspace_root=str(ws),
            repo_root=repo_root,
            env_mode="dotenv",
            request_id="req-init",
            auth_checked=True,
            rate_limited=False,
            policy={},
            build_response=_build_response,
        )
        _must(isinstance(init_resp, dict), "llm_providers_init response must be dict")
        _must(str(init_resp.get("request_id") or "") == "req-init", "request_id mismatch")
        _must(str(init_resp.get("status") or "") in {"OK", "FAIL"}, "init status must be OK/FAIL")

    print(
        json.dumps(
            {
                "status": "OK",
                "init_status": init_resp.get("status"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
