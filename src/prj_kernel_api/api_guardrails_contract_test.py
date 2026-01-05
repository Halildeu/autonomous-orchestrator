"""Contract test for PRJ-KERNEL-API guardrails (stdlib-only, deterministic)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
from pathlib import Path

import src.prj_kernel_api.api_guardrails as guardrails


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _reset_rate_state() -> None:
    guardrails._rate_state["minute"] = None
    guardrails._rate_state["count"] = 0
    guardrails._rate_state["limit"] = None


def _reset_concurrency_state() -> None:
    guardrails._concurrency_state["limit"] = None
    guardrails._concurrency_state["semaphore"] = None


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_guardrails_demo"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    env_mode = "process"
    prev_env = {
        "KERNEL_API_TOKEN": os.environ.get("KERNEL_API_TOKEN"),
        "KERNEL_API_HMAC_SECRET": os.environ.get("KERNEL_API_HMAC_SECRET"),
        "KERNEL_API_AUTH_MODE": os.environ.get("KERNEL_API_AUTH_MODE"),
        "KERNEL_API_RATE_LIMIT_PER_MINUTE": os.environ.get("KERNEL_API_RATE_LIMIT_PER_MINUTE"),
        "KERNEL_API_MAX_CONCURRENT": os.environ.get("KERNEL_API_MAX_CONCURRENT"),
    }
    os.environ["KERNEL_API_TOKEN"] = "TEST_TOKEN"
    os.environ["KERNEL_API_HMAC_SECRET"] = "TEST_SECRET"
    os.environ["KERNEL_API_AUTH_MODE"] = "bearer"
    os.environ["KERNEL_API_RATE_LIMIT_PER_MINUTE"] = "1"
    os.environ["KERNEL_API_MAX_CONCURRENT"] = "1"

    try:
        policy = guardrails.load_guardrails_policy(str(ws))

        ok, error, checked = guardrails.verify_auth(
            headers={"Authorization": "Bearer TEST_TOKEN"},
            body_bytes=b"{}",
            policy=policy,
            workspace_root=str(ws),
            env_mode=env_mode,
        )
        if not ok or error or not checked:
            raise SystemExit("Guardrails test failed: bearer auth should pass.")

        ok, error, _checked = guardrails.verify_auth(
            headers={},
            body_bytes=b"{}",
            policy=policy,
            workspace_root=str(ws),
            env_mode=env_mode,
        )
        if ok or error != "KERNEL_API_UNAUTHORIZED":
            raise SystemExit("Guardrails test failed: missing bearer auth should fail.")

        os.environ["KERNEL_API_AUTH_MODE"] = "hmac"
        body = b'{"ping":"pong"}'
        signature = hmac.new(b"TEST_SECRET", body, hashlib.sha256).hexdigest()
        ok, error, checked = guardrails.verify_auth(
            headers={"X-Signature": signature},
            body_bytes=body,
            policy=policy,
            workspace_root=str(ws),
            env_mode=env_mode,
        )
        if not ok or error or not checked:
            raise SystemExit("Guardrails test failed: hmac auth should pass.")

        ok, error, _checked = guardrails.verify_auth(
            headers={"X-Signature": "bad"},
            body_bytes=body,
            policy=policy,
            workspace_root=str(ws),
            env_mode=env_mode,
        )
        if ok or error != "KERNEL_API_UNAUTHORIZED":
            raise SystemExit("Guardrails test failed: bad hmac should fail.")

        _reset_rate_state()
        ok, error, rate_limited = guardrails.enforce_limits(
            policy=policy,
            workspace_root=str(ws),
            env_mode=env_mode,
            body_bytes=b"{}",
            json_obj={},
        )
        if not ok or error or rate_limited:
            raise SystemExit("Guardrails test failed: first rate limit check should pass.")
        ok, error, rate_limited = guardrails.enforce_limits(
            policy=policy,
            workspace_root=str(ws),
            env_mode=env_mode,
            body_bytes=b"{}",
            json_obj={},
        )
        if ok or error != "KERNEL_API_RATE_LIMITED" or not rate_limited:
            raise SystemExit("Guardrails test failed: rate limit should trigger.")

        _reset_concurrency_state()
        ok, error, sem = guardrails.acquire_concurrency(policy, str(ws), env_mode=env_mode)
        if not ok or error or sem is None:
            raise SystemExit("Guardrails test failed: first concurrency acquire should pass.")
        ok, error, _sem2 = guardrails.acquire_concurrency(policy, str(ws), env_mode=env_mode)
        if ok or error != "KERNEL_API_CONCURRENCY_LIMIT":
            raise SystemExit("Guardrails test failed: concurrency limit should trigger.")
        guardrails.release_concurrency(sem)

        redacted = guardrails.redact(
            {"api_key": "SECRET", "nested": {"Authorization": "Bearer SECRET", "token": "SECRET"}},
            ["*KEY*", "authorization", "*TOKEN*"],
        )
        if redacted.get("api_key") != "***REDACTED***":
            raise SystemExit("Guardrails test failed: api_key should be redacted.")
        nested = redacted.get("nested")
        if not isinstance(nested, dict) or nested.get("Authorization") != "***REDACTED***":
            raise SystemExit("Guardrails test failed: authorization should be redacted.")

        print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))
    finally:
        for key, value in prev_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
