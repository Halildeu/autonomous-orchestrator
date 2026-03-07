"""Contract test for workspace Codex home bootstrap."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import tomllib

from src.prj_kernel_api.codex_home import ensure_codex_home


def _fail(code: str, message: str) -> None:
    print(json.dumps({"status": "FAIL", "error_code": code, "message": message}, sort_keys=True))
    raise SystemExit(1)


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = repo_root / ".cache" / "ws_codex_home_demo"
    if ws.exists():
        shutil.rmtree(ws)

    env_overrides = ensure_codex_home(str(ws))
    codex_home = env_overrides.get("CODEX_HOME")
    if not codex_home:
        _fail("CODEX_HOME_MISSING", "CODEX_HOME not returned.")

    config_path = Path(codex_home) / "config.toml"
    if not config_path.exists():
        _fail("CODEX_HOME_CONFIG_MISSING", "CODEX_HOME config.toml missing.")

    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if cfg.get("model") != "gpt-5.3-codex":
        _fail("CODEX_HOME_INVALID", "model mismatch.")
    if cfg.get("review_model") != "gpt-5.4":
        _fail("CODEX_HOME_INVALID", "review_model mismatch.")
    if cfg.get("approval_policy") != "never":
        _fail("CODEX_HOME_INVALID", "approval_policy mismatch.")
    if cfg.get("sandbox_mode") != "workspace-write":
        _fail("CODEX_HOME_INVALID", "sandbox_mode mismatch.")

    sandbox = cfg.get("sandbox_workspace_write")
    if not isinstance(sandbox, dict) or sandbox.get("network_access") is not False:
        _fail("CODEX_HOME_INVALID", "network_access must be false.")

    if cfg.get("project_doc_max_bytes") != 65536:
        _fail("CODEX_HOME_INVALID", "project_doc_max_bytes mismatch.")
    if cfg.get("model_auto_compact_token_limit") != 24000:
        _fail("CODEX_HOME_INVALID", "model_auto_compact_token_limit mismatch.")
    if cfg.get("model_reasoning_effort") != "medium":
        _fail("CODEX_HOME_INVALID", "model_reasoning_effort mismatch.")

    fallback = cfg.get("project_doc_fallback_filenames")
    if not isinstance(fallback, list) or "AGENTS.md" not in fallback:
        _fail("CODEX_HOME_INVALID", "fallback list missing AGENTS.md.")

    print(json.dumps({"status": "OK", "codex_home": str(codex_home)}, sort_keys=True))


if __name__ == "__main__":
    main()
