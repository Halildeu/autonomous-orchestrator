"""Program-led Codex config sanity check (workspace-scoped, deterministic)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.prj_kernel_api.codex_home import ensure_codex_home, resolve_effective_codex_config


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_toml(path: Path) -> Dict[str, Any]:
    return tomllib.loads(_read_text(path))


def _scan_duplicates(text: str) -> Tuple[List[str], List[str]]:
    key_re = re.compile(r"^([A-Za-z0-9_.-]+)\s*=")
    table_re = re.compile(r"^\[([A-Za-z0-9_.-]+)\]")
    seen_keys: Dict[str, set[str]] = {}
    seen_tables: set[str] = set()
    dup_keys: List[str] = []
    dup_tables: List[str] = []
    current_table = ""
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        table_match = table_re.match(stripped)
        if table_match:
            current_table = table_match.group(1)
            if current_table in seen_tables:
                dup_tables.append(f"{idx}:{current_table}")
            else:
                seen_tables.add(current_table)
            continue
        key_match = key_re.match(stripped)
        if key_match:
            key = key_match.group(1)
            scope = current_table or "root"
            if scope not in seen_keys:
                seen_keys[scope] = set()
            if key in seen_keys[scope]:
                dup_keys.append(f"{idx}:{scope}.{key}")
            else:
                seen_keys[scope].add(key)
    return dup_keys[:20], dup_tables[:20]


def _effective_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    sandbox = cfg.get("sandbox_workspace_write")
    network_access = None
    if isinstance(sandbox, dict):
        network_access = sandbox.get("network_access")
    return {
        "model": cfg.get("model"),
        "review_model": cfg.get("review_model"),
        "model_provider": cfg.get("model_provider"),
        "approval_policy": cfg.get("approval_policy"),
        "sandbox_mode": cfg.get("sandbox_mode"),
        "project_doc_max_bytes": cfg.get("project_doc_max_bytes"),
        "project_doc_fallback_filenames": cfg.get("project_doc_fallback_filenames"),
        "project_root_markers": cfg.get("project_root_markers"),
        "model_reasoning_effort": cfg.get("model_reasoning_effort"),
        "model_reasoning_summary": cfg.get("model_reasoning_summary"),
        "model_verbosity": cfg.get("model_verbosity"),
        "model_auto_compact_token_limit": cfg.get("model_auto_compact_token_limit"),
        "web_search": cfg.get("web_search"),
        "sandbox_workspace_write.network_access": network_access,
    }


def _compare(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    mismatches: List[str] = []
    for key, exp in expected.items():
        act = actual.get(key)
        if exp != act:
            mismatches.append(key)
    return mismatches


def _invariants_ok(actual: Dict[str, Any]) -> bool:
    return (
        actual.get("approval_policy") == "never"
        and actual.get("sandbox_mode") == "workspace-write"
        and actual.get("sandbox_workspace_write.network_access") is False
        and actual.get("project_doc_max_bytes") == 65536
        and actual.get("model_provider") == "openai"
        and isinstance(actual.get("project_doc_fallback_filenames"), list)
        and "AGENTS.md" in actual.get("project_doc_fallback_filenames")
    )


def run(workspace_root: str) -> Dict[str, Any]:
    resolved = resolve_effective_codex_config(workspace_root)
    env_overrides = ensure_codex_home(workspace_root)
    codex_home = Path(env_overrides.get("CODEX_HOME", ""))
    runtime_path = codex_home / "config.toml"
    repo_template_path = Path(str(resolved.get("template_path") or ""))

    repo_exists = repo_template_path.exists()
    runtime_exists = runtime_path.exists()

    dup_keys_repo: List[str] = []
    dup_tables_repo: List[str] = []
    dup_keys_runtime: List[str] = []
    dup_tables_runtime: List[str] = []

    repo_cfg: Dict[str, Any] = {}
    runtime_cfg: Dict[str, Any] = {}
    repo_parse_ok = repo_exists
    runtime_parse_ok = False

    if repo_exists:
        text = _read_text(repo_template_path)
        dup_keys_repo, dup_tables_repo = _scan_duplicates(text)
        repo_cfg = resolved.get("effective_config") if isinstance(resolved.get("effective_config"), dict) else {}

    if runtime_exists:
        text = _read_text(runtime_path)
        dup_keys_runtime, dup_tables_runtime = _scan_duplicates(text)
        try:
            runtime_cfg = _load_toml(runtime_path)
            runtime_parse_ok = True
        except Exception:
            runtime_parse_ok = False

    expected = _effective_config(repo_cfg) if repo_parse_ok else {}
    actual = _effective_config(runtime_cfg) if runtime_parse_ok else {}
    mismatches = _compare(expected, actual) if expected and actual else []
    invariants_ok = _invariants_ok(actual) if runtime_parse_ok else False

    status = "OK"
    if not repo_exists or not runtime_exists:
        status = "FAIL"
    elif not repo_parse_ok or not runtime_parse_ok:
        status = "FAIL"
    elif not invariants_ok:
        status = "FAIL"
    elif mismatches:
        status = "WARN"

    return {
        "status": status,
        "repo_template_exists": repo_exists,
        "runtime_exists": runtime_exists,
        "duplicates_repo": len(dup_keys_repo) + len(dup_tables_repo),
        "duplicates_runtime": len(dup_keys_runtime) + len(dup_tables_runtime),
        "duplicate_keys_repo": dup_keys_repo,
        "duplicate_tables_repo": dup_tables_repo,
        "duplicate_keys_runtime": dup_keys_runtime,
        "duplicate_tables_runtime": dup_tables_runtime,
        "mismatch_fields": mismatches,
        "invariants_ok": invariants_ok,
        "notes": [
            "PROGRAM_LED=true",
            f"CODEX_HOME={codex_home}",
            f"template_path={repo_template_path}",
            f"runtime_path={runtime_path}",
            "overlay_sources=" + ",".join(
                [str(item) for item in resolved.get("overlay_sources", []) if isinstance(item, str)]
            ),
        ],
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-root", required=True)
    args = ap.parse_args()
    result = run(args.workspace_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
