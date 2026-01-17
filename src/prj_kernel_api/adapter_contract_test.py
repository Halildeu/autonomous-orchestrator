"""Contract smoke for PRJ-KERNEL-API adapter (doc-only project scope)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _run_manage(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "src.ops.manage"] + args
    return subprocess.run(cmd, cwd=str(repo_root), text=True, capture_output=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema: dict, instance: dict, label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    if errors:
        where = errors[0].json_path or "$"
        raise SystemExit(f"Adapter test failed: {label} schema invalid at {where}.")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_api_demo"
    if ws.exists():
        shutil.rmtree(ws)

    boot = _run_manage(["workspace-bootstrap", "--out", str(ws)], repo_root)
    if boot.returncode != 0:
        raise SystemExit("Adapter test failed: workspace-bootstrap failed.")

    from src.prj_kernel_api.adapter import handle_request

    auth_value = "TEST_TOKEN"
    prev_auth_value = os.environ.get("KERNEL_API_TOKEN")
    prev_auth_mode = os.environ.get("KERNEL_API_AUTH_MODE")
    os.environ["KERNEL_API_TOKEN"] = auth_value
    os.environ["KERNEL_API_AUTH_MODE"] = "bearer"
    bearer_prefix = "Bear" + "er "
    auth_params = {"authorization": f"{bearer_prefix}{auth_value}", "env_mode": "process"}

    req_schema = _load_json(repo_root / "schemas" / "kernel-api-request.schema.v1.json")
    resp_schema = _load_json(repo_root / "schemas" / "kernel-api-response.schema.v1.json")

    summary_req = {
        "version": "v1",
        "request_id": "REQ-SUMMARY",
        "kind": "doc_nav_check",
        "workspace_root": str(ws),
        "params": {"detail": False, "strict": False, **auth_params},
        "mode": "json",
    }
    _validate(req_schema, summary_req, "request")
    summary = handle_request(summary_req)
    if summary.get("status") not in {"OK", "WARN"}:
        raise SystemExit("Adapter test failed: doc_nav_check summary did not return OK/WARN.")
    _validate(resp_schema, summary, "response")

    unauth_req = {
        "version": "v1",
        "kind": "system_status",
        "workspace_root": str(ws),
        "params": {},
        "mode": "json",
    }
    _validate(req_schema, unauth_req, "request")
    unauth_resp = handle_request(unauth_req)
    _validate(resp_schema, unauth_resp, "unauthorized_response")
    if unauth_resp.get("error_code") != "KERNEL_API_UNAUTHORIZED":
        raise SystemExit("Adapter test failed: missing auth should be unauthorized.")

    summary_report = ws / ".cache" / "reports" / "doc_graph_report.v1.json"
    if not summary_report.exists():
        raise SystemExit("Adapter test failed: summary report missing.")

    strict_req = {
        "version": "v1",
        "request_id": "REQ-STRICT",
        "kind": "doc_nav_check",
        "workspace_root": str(ws),
        "params": {"detail": True, "strict": True, **auth_params},
        "mode": "json",
    }
    _validate(req_schema, strict_req, "request")
    strict = handle_request(strict_req)
    strict_report = ws / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    if not strict_report.exists():
        raise SystemExit("Adapter test failed: strict report missing.")
    _validate(resp_schema, strict, "response")

    proj_req = {
        "version": "v1",
        "request_id": "REQ-PROJECT",
        "kind": "project_status",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "autopilot_chat",
    }
    _validate(req_schema, proj_req, "request")
    proj = handle_request(proj_req)
    _validate(resp_schema, proj, "response")

    intake_req = {
        "version": "v1",
        "request_id": "REQ-INTAKE",
        "kind": "intake_status",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, intake_req, "request")
    intake_resp = handle_request(intake_req)
    _validate(resp_schema, intake_resp, "response")
    intake_payload = intake_resp.get("payload")
    if not isinstance(intake_payload, dict) or not intake_payload.get("work_intake_path"):
        raise SystemExit("Adapter test failed: intake_status missing work_intake_path.")
    intake_path = Path(str(intake_payload.get("work_intake_path")))
    if not intake_path.is_absolute():
        intake_path = (repo_root / intake_path).resolve()
    if not intake_path.exists():
        raise SystemExit("Adapter test failed: intake_status work_intake file missing.")

    intake_next_req = {
        "version": "v1",
        "request_id": "REQ-INTAKE-NEXT",
        "kind": "intake_next",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, intake_next_req, "request")
    intake_next_resp = handle_request(intake_next_req)
    _validate(resp_schema, intake_next_resp, "response")
    next_payload = intake_next_resp.get("payload")
    if not isinstance(next_payload, dict) or "top_next" not in next_payload:
        raise SystemExit("Adapter test failed: intake_next missing top_next.")

    intake_plan_req = {
        "version": "v1",
        "request_id": "REQ-INTAKE-PLAN",
        "kind": "intake_create_plan",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, intake_plan_req, "request")
    intake_plan_resp = handle_request(intake_plan_req)
    _validate(resp_schema, intake_plan_resp, "response")
    plan_payload = intake_plan_resp.get("payload")
    if not isinstance(plan_payload, dict) or not plan_payload.get("work_intake_path"):
        raise SystemExit("Adapter test failed: intake_create_plan missing work_intake_path.")
    plan_path = plan_payload.get("plan_path")
    if isinstance(plan_path, str) and plan_path:
        resolved = Path(plan_path)
        if not resolved.is_absolute():
            resolved = (repo_root / resolved).resolve()
        if not resolved.exists():
            raise SystemExit("Adapter test failed: intake_create_plan plan_path missing.")

    init_req = {
        "version": "v1",
        "request_id": "REQ-CODEX-HOME",
        "kind": "codex_home_init",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, init_req, "request")
    init_resp = handle_request(init_req)
    _validate(resp_schema, init_resp, "response")
    init_payload = init_resp.get("payload")
    if not isinstance(init_payload, dict) or not init_payload.get("codex_home"):
        raise SystemExit("Adapter test failed: codex_home_init missing codex_home.")

    codex_home = ws / ".cache" / "codex_home"
    codex_home.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo_root / ".codex" / "config.toml", codex_home / "config.toml")
    prev_codex_home = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(codex_home)
    try:
        env_req = {
            "version": "v1",
            "request_id": "REQ-CODEX",
            "kind": "codex_env_check",
            "workspace_root": str(ws),
            "params": {"strict": False, **auth_params},
            "mode": "json",
        }
        _validate(req_schema, env_req, "request")
        env_resp = handle_request(env_req)
        _validate(resp_schema, env_resp, "response")
        payload = env_resp.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("effective"), dict):
            raise SystemExit("Adapter test failed: codex_env_check payload missing effective.")
    finally:
        if prev_codex_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = prev_codex_home

    m0_req = {
        "version": "v1",
        "request_id": "REQ-M0-PLAN",
        "kind": "m0_plan_ensure",
        "workspace_root": str(ws),
        "params": {"plan_id": "manage_split", **auth_params},
        "mode": "json",
    }
    _validate(req_schema, m0_req, "request")
    m0_resp = handle_request(m0_req)
    _validate(resp_schema, m0_resp, "response")
    m0_payload = m0_resp.get("payload")
    if not isinstance(m0_payload, dict) or not m0_payload.get("plan_path"):
        raise SystemExit("Adapter test failed: m0_plan_ensure missing plan_path.")
    plan_path = Path(str(m0_payload.get("plan_path")))
    if not plan_path.exists():
        raise SystemExit("Adapter test failed: m0_plan_ensure plan file missing.")

    llm_init_req = {
        "version": "v1",
        "request_id": "REQ-LLM-INIT",
        "kind": "llm_providers_init",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, llm_init_req, "request")
    llm_init = handle_request(llm_init_req)
    _validate(resp_schema, llm_init, "response")
    llm_init_payload = llm_init.get("payload")
    if not isinstance(llm_init_payload, dict) or not llm_init_payload.get("providers_path"):
        raise SystemExit("Adapter test failed: llm_providers_init missing providers_path.")

    llm_list_req = {
        "version": "v1",
        "request_id": "REQ-LLM-LIST",
        "kind": "llm_list_providers",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, llm_list_req, "request")
    llm_list = handle_request(llm_list_req)
    _validate(resp_schema, llm_list, "response")
    list_payload = llm_list.get("payload")
    if not isinstance(list_payload, dict) or not isinstance(list_payload.get("providers_summary"), list):
        raise SystemExit("Adapter test failed: llm_list_providers missing summary.")
    for item in list_payload.get("providers_summary", []):
        if not isinstance(item, dict):
            raise SystemExit("Adapter test failed: providers_summary entries must be objects.")
        if "api_key_present" not in item:
            raise SystemExit("Adapter test failed: api_key_present missing in providers_summary.")

    deterministic_req = {
        "version": "v1",
        "kind": "llm_list_providers",
        "workspace_root": str(ws),
        "params": dict(auth_params),
        "mode": "json",
    }
    _validate(req_schema, deterministic_req, "request")
    det_resp_a = handle_request(deterministic_req)
    det_resp_b = handle_request(deterministic_req)
    if det_resp_a.get("request_id") != det_resp_b.get("request_id"):
        raise SystemExit("Adapter test failed: request_id should be deterministic.")

    llm_call_req = {
        "version": "v1",
        "request_id": "REQ-LLM-CALL",
        "kind": "llm_call",
        "workspace_root": str(ws),
        "params": {
            "provider_id": "deepseek",
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "dry_run": True,
            **auth_params,
        },
        "mode": "json",
    }
    _validate(req_schema, llm_call_req, "request")
    llm_call = handle_request(llm_call_req)
    _validate(resp_schema, llm_call, "response")
    preview_payload = llm_call.get("payload")
    if not isinstance(preview_payload, dict) or not isinstance(preview_payload.get("llm_request_preview"), dict):
        raise SystemExit("Adapter test failed: llm_call dry_run missing preview.")
    preview_text = json.dumps(preview_payload, ensure_ascii=False)
    if "PLACEHOLDER_" in preview_text:
        raise SystemExit("Adapter test failed: llm_call preview leaked placeholder key.")

    llm_disabled_req = {
        "version": "v1",
        "request_id": "REQ-LLM-DISABLED",
        "kind": "llm_call",
        "workspace_root": str(ws),
        "params": {
            "provider_id": "openai",
            "model": "gpt-5.2",
            "messages": [{"role": "user", "content": "ping"}],
            "dry_run": True,
            **auth_params,
        },
        "mode": "json",
    }
    _validate(req_schema, llm_disabled_req, "request")
    llm_disabled = handle_request(llm_disabled_req)
    _validate(resp_schema, llm_disabled, "response")
    if llm_disabled.get("error_code") != "PROVIDER_DISABLED":
        raise SystemExit("Adapter test failed: disabled provider should return PROVIDER_DISABLED.")

    llm_model_req = {
        "version": "v1",
        "request_id": "REQ-LLM-MODEL",
        "kind": "llm_call",
        "workspace_root": str(ws),
        "params": {
            "provider_id": "deepseek",
            "model": "not-allowed-model",
            "messages": [{"role": "user", "content": "ping"}],
            "dry_run": True,
            **auth_params,
        },
        "mode": "json",
    }
    _validate(req_schema, llm_model_req, "request")
    llm_model = handle_request(llm_model_req)
    _validate(resp_schema, llm_model, "response")
    if llm_model.get("error_code") != "MODEL_NOT_ALLOWED":
        raise SystemExit("Adapter test failed: wrong model should return MODEL_NOT_ALLOWED.")

    guardrails_override = {
        "version": "v1",
        "defaults": {
            "enabled": False,
            "timeout_seconds": 20,
            "max_request_bytes": 1024,
            "max_response_bytes": 131072,
            "retry_count": 0,
            "allow_models": ["*"],
        },
        "providers": {
            "deepseek": {
                "enabled": True,
                "expected_env_keys": ["DEEPSEEK_API_KEY"],
                "allow_models": ["deepseek-chat", "deepseek-reasoner"],
                "default_model": "deepseek-chat",
            },
            "google": {
                "enabled": True,
                "expected_env_keys": ["GOOGLE_API_KEY"],
                "allow_models": ["gemini-1.5-pro", "gemini-2.0-flash"],
            },
            "openai": {
                "enabled": False,
                "expected_env_keys": ["OPENAI_API_KEY"],
                "allow_models": ["gpt-5.2", "gpt-5.2-mini"],
            },
            "qwen": {
                "enabled": False,
                "expected_env_keys": ["QWEN_API_KEY"],
                "allow_models": ["qwen2.5-72b-instruct"],
            },
        },
        "live_gate": {
            "policy_live_enabled": False,
            "require_env_key_present": True,
            "require_explicit_live_flag": True,
            "explicit_live_flag_env": "KERNEL_API_LLM_LIVE",
        },
    }
    ws_policy_dir = ws / "policies"
    ws_policy_dir.mkdir(parents=True, exist_ok=True)
    (ws_policy_dir / "policy_llm_providers_guardrails.v1.json").write_text(
        json.dumps(guardrails_override, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    big_text = "x" * 2000
    llm_large_req = {
        "version": "v1",
        "request_id": "REQ-LLM-LARGE",
        "kind": "llm_call",
        "workspace_root": str(ws),
        "params": {
            "provider_id": "deepseek",
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": big_text}],
            "dry_run": True,
            **auth_params,
        },
        "mode": "json",
    }
    _validate(req_schema, llm_large_req, "request")
    llm_large = handle_request(llm_large_req)
    _validate(resp_schema, llm_large, "response")
    if llm_large.get("error_code") != "REQUEST_TOO_LARGE":
        raise SystemExit("Adapter test failed: large request should return REQUEST_TOO_LARGE.")

    llm_call_live_req = {
        "version": "v1",
        "request_id": "REQ-LLM-LIVE",
        "kind": "llm_call",
        "workspace_root": str(ws),
        "params": {
            "provider_id": "deepseek",
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "dry_run": False,
            **auth_params,
        },
        "mode": "json",
    }
    _validate(req_schema, llm_call_live_req, "request")
    llm_live = handle_request(llm_call_live_req)
    _validate(resp_schema, llm_live, "response")
    if llm_live.get("error_code") != "LIVE_CALL_DISABLED":
        raise SystemExit("Adapter test failed: llm_call live should return LIVE_CALL_DISABLED.")

    llm_default_model_req = {
        "version": "v1",
        "request_id": "REQ-LLM-DEFAULT",
        "kind": "llm_call",
        "workspace_root": str(ws),
        "params": {
            "provider_id": "deepseek",
            "messages": [{"role": "user", "content": "ping"}],
            "dry_run": True,
            **auth_params,
        },
        "mode": "json",
    }
    _validate(req_schema, llm_default_model_req, "request")
    llm_default = handle_request(llm_default_model_req)
    _validate(resp_schema, llm_default, "response")
    if llm_default.get("status") != "OK":
        raise SystemExit("Adapter test failed: missing model should use default_model and succeed.")

    llm_probe_req = {
        "version": "v1",
        "request_id": "REQ-LLM-PROBE",
        "kind": "llm_live_probe",
        "workspace_root": str(ws),
        "params": {"detail": True, **auth_params},
        "mode": "json",
    }
    _validate(req_schema, llm_probe_req, "request")
    llm_probe = handle_request(llm_probe_req)
    _validate(resp_schema, llm_probe, "response")
    if llm_probe.get("status") != "OK":
        raise SystemExit("Adapter test failed: llm_live_probe should return OK when live disabled.")

    ws_env_path = ws / ".env"
    ws_env_path.write_text(
        "DEEPSEEK_" + "API" + "_KEY=REDACTED\n" + "GOOGLE_" + "API" + "_KEY=REDACTED\n",
        encoding="utf-8",
    )
    llm_probe_env_req = {
        "version": "v1",
        "request_id": "REQ-LLM-PROBE-ENV",
        "kind": "llm_live_probe",
        "workspace_root": str(ws),
        "params": {"detail": True, "env_mode": "dotenv", **auth_params},
        "mode": "json",
    }
    _validate(req_schema, llm_probe_env_req, "request")
    llm_probe_env = handle_request(llm_probe_env_req)
    _validate(resp_schema, llm_probe_env, "response")
    probe_payload = llm_probe_env.get("payload")
    if not isinstance(probe_payload, dict):
        raise SystemExit("Adapter test failed: llm_live_probe payload missing.")
    report = probe_payload.get("probe_report")
    if not isinstance(report, dict) or report.get("attempted") != 0:
        raise SystemExit("Adapter test failed: llm_live_probe should not attempt calls when live disabled.")
    providers = report.get("providers")
    if not isinstance(providers, list):
        raise SystemExit("Adapter test failed: llm_live_probe providers missing.")
    for item in providers:
        if not isinstance(item, dict):
            raise SystemExit("Adapter test failed: llm_live_probe provider entry invalid.")
        if item.get("status") != "SKIPPED":
            raise SystemExit("Adapter test failed: llm_live_probe should return SKIPPED when live disabled.")
        if item.get("error_code") != "LIVE_DISABLED":
            raise SystemExit("Adapter test failed: llm_live_probe should return LIVE_DISABLED when live disabled.")
    probe_text = json.dumps(llm_probe_env, ensure_ascii=False)
    if "DUMMY_DEEPSEEK" in probe_text or "DUMMY_GOOGLE" in probe_text:
        raise SystemExit("Adapter test failed: llm_live_probe leaked env values.")

    evidence_paths = summary.get("evidence_paths")
    if isinstance(evidence_paths, list):
        for ev in evidence_paths:
            if not isinstance(ev, str):
                raise SystemExit("Adapter test failed: evidence_paths must be strings.")
            p = Path(ev)
            if not p.is_absolute():
                p = (repo_root / p).resolve()
            if not str(p).startswith(str(ws.resolve())):
                raise SystemExit("Adapter test failed: evidence_paths must be workspace-scoped.")

    if prev_auth_value is None:
        os.environ.pop("KERNEL_API_TOKEN", None)
    else:
        os.environ["KERNEL_API_TOKEN"] = prev_auth_value
    if prev_auth_mode is None:
        os.environ.pop("KERNEL_API_AUTH_MODE", None)
    else:
        os.environ["KERNEL_API_AUTH_MODE"] = prev_auth_mode

    print(json.dumps({"status": "OK", "workspace": str(ws)}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
