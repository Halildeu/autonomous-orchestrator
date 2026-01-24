from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_contract_workspace_root(*, repo_root: Path) -> Path:
    ws = repo_root / ".cache" / "ws_customer_default"
    if ws.exists():
        return ws
    fallback = repo_root / ".cache" / "ws_extension_contract"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    manifest_path = Path(__file__).resolve().parents[1] / "extension.manifest.v1.json"
    if not manifest_path.exists():
        raise SystemExit("otel pack contract_test: FAIL (manifest missing)")

    manifest = _load_json(manifest_path)
    schema_path = repo_root / "schemas" / "extension-manifest.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(manifest)

    docs_ref = manifest.get("docs_ref")
    if not isinstance(docs_ref, str) or not docs_ref:
        raise SystemExit("otel pack contract_test: FAIL (docs_ref missing)")
    docs_path = docs_ref.split("#", 1)[0]
    if docs_path and not (repo_root / docs_path).exists():
        raise SystemExit("otel pack contract_test: FAIL (docs_ref path missing)")

    ai_context_refs = manifest.get("ai_context_refs")
    if not isinstance(ai_context_refs, list) or not ai_context_refs:
        raise SystemExit("otel pack contract_test: FAIL (ai_context_refs missing)")
    for ref in ai_context_refs:
        if not isinstance(ref, str) or not ref:
            raise SystemExit("otel pack contract_test: FAIL (ai_context_refs invalid)")
        if not (repo_root / ref).exists():
            raise SystemExit("otel pack contract_test: FAIL (ai_context_refs path missing)")

    from src.orchestrator.observability.otel_bridge import attach_trace_meta

    trace_meta_schema_path = repo_root / "schemas" / "trace-meta.schema.v1.json"
    trace_meta_schema = _load_json(trace_meta_schema_path)
    Draft202012Validator.check_schema(trace_meta_schema)

    dummy_run_id = "RUN-OTEL-001"
    dummy_summary = {"run_id": dummy_run_id, "status": "COMPLETED", "result_state": "COMPLETED"}
    trace_meta = attach_trace_meta(
        dummy_summary,
        workspace=repo_root,
        out_dir=repo_root / "evidence",
        run_id=dummy_run_id,
    )
    Draft202012Validator(trace_meta_schema).validate(trace_meta)
    if not isinstance(dummy_summary.get("trace_meta"), dict):
        raise SystemExit("otel pack contract_test: FAIL (trace_meta not attached)")
    if str(trace_meta.get("run_id") or "") != dummy_run_id:
        raise SystemExit("otel pack contract_test: FAIL (trace_meta run_id mismatch)")
    if str(trace_meta.get("work_item_kind") or "") != "RUN":
        raise SystemExit("otel pack contract_test: FAIL (trace_meta work_item_kind must be RUN)")

    evidence_paths = trace_meta.get("evidence_paths")
    if not isinstance(evidence_paths, list) or not evidence_paths:
        raise SystemExit("otel pack contract_test: FAIL (trace_meta evidence_paths missing)")
    if not any("summary.json" in str(p) for p in evidence_paths):
        raise SystemExit("otel pack contract_test: FAIL (trace_meta evidence_paths missing summary.json)")

    runner_path = repo_root / "src" / "orchestrator" / "runner_execute.py"
    runner_text = runner_path.read_text(encoding="utf-8")
    if "attach_trace_meta" not in runner_text:
        raise SystemExit("otel pack contract_test: FAIL (runner_execute missing trace_meta hook)")

    from src.ops.extension_run import run_extension_run

    ws_root = _resolve_contract_workspace_root(repo_root=repo_root)
    ws = ws_root / ".cache" / "ws_extension_contract"
    ws.mkdir(parents=True, exist_ok=True)

    extension_id = str(manifest.get("extension_id") or "").strip()
    res = run_extension_run(workspace_root=ws, extension_id=extension_id, mode="report", chat=False)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("otel pack contract_test: FAIL (extension_run status invalid)")
    if res.get("network_allowed") is not False:
        raise SystemExit("otel pack contract_test: FAIL (network must be disabled)")

    print("otel pack contract_test: PASS")
    print(json.dumps({"status": "OK", "extension_id": extension_id, "trace_meta": trace_meta}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
