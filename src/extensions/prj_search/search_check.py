from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _rel_from_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _load_search_adapter_module():
    adapter_path = _repo_root() / "extensions" / "PRJ-SEARCH" / "search_adapter.py"
    spec = importlib.util.spec_from_file_location("prj_search.search_adapter_runtime", adapter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"search_adapter module spec not available: {adapter_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Search Check v1")
    lines.append("")
    lines.append(f"- generated_at: {report.get('generated_at', '')}")
    lines.append(f"- status: {report.get('status', '')}")
    lines.append(f"- scope: {report.get('scope', '')}")
    lines.append(f"- query: {report.get('query', '')}")
    lines.append(f"- mode_requested: {report.get('mode_requested', '')}")
    lines.append(f"- mode_actual: {report.get('mode_actual', '')}")
    lines.append(f"- engine: {report.get('engine', '')}")
    lines.append(f"- duration_ms: {report.get('duration_ms', 0)}")
    lines.append("")
    lines.append("## Capabilities")
    caps = report.get("capabilities_summary") if isinstance(report.get("capabilities_summary"), dict) else {}
    lines.append(f"- contract_id: {caps.get('contract_id', '')}")
    lines.append(f"- auto_mode_primary: {caps.get('auto_mode_primary', '')}")
    lines.append(f"- adapter_count: {caps.get('adapter_count', 0)}")
    lines.append("")
    lines.append("## Index")
    index_before = report.get("index_before") if isinstance(report.get("index_before"), dict) else {}
    index_after = report.get("index_after") if isinstance(report.get("index_after"), dict) else {}
    lines.append(f"- before_status: {index_before.get('status', '')}")
    lines.append(f"- after_status: {index_after.get('status', '')}")
    lines.append(f"- before_adapter: {index_before.get('adapter_id', '')}")
    lines.append(f"- after_adapter: {index_after.get('adapter_id', '')}")
    lines.append("")
    lines.append("## Search")
    lines.append(f"- search_status: {report.get('search_status', '')}")
    lines.append(f"- hits: {report.get('hits', 0)}")
    lines.append("")
    lines.append("## Notes")
    notes = report.get("notes") if isinstance(report.get("notes"), list) else []
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Evidence")
    evidence = report.get("evidence_paths") if isinstance(report.get("evidence_paths"), list) else []
    for item in evidence:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def run_search_check(
    *,
    workspace_root: Path,
    scope: str = "ssot",
    query: str = "policy",
    mode: str = "keyword",
    chat: bool = True,
) -> dict[str, Any]:
    workspace_root = Path(workspace_root).resolve()
    scope_norm = str(scope or "ssot").strip().lower()
    if scope_norm not in {"ssot", "repo"}:
        scope_norm = "ssot"
    mode_norm = str(mode or "keyword").strip().lower()
    if mode_norm not in {"keyword", "semantic", "auto"}:
        mode_norm = "keyword"
    query_norm = str(query or "policy").strip() or "policy"

    out_json = workspace_root / ".cache" / "reports" / "search_check.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "search_check.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    try:
        adapter_module = _load_search_adapter_module()
        manager_cls = getattr(adapter_module, "KeywordIndexManager", None)
        if manager_cls is None:
            raise RuntimeError("KeywordIndexManager missing in search_adapter")

        manager = manager_cls(_repo_root(), workspace_root)
        index_before = manager.status(scope_norm)
        capabilities = manager.capabilities(scope_norm)

        t0 = time.monotonic()
        search_payload = manager.search(
            query_norm,
            scope=scope_norm,
            search_mode=mode_norm,
            pattern_mode="auto",
            limit=20,
            auto_build=True,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        index_after = manager.status(scope_norm)

        search_status = str(search_payload.get("status") or "OK").strip().upper()
        hits = len(search_payload.get("hits") or []) if isinstance(search_payload.get("hits"), list) else 0
        engine = str(search_payload.get("engine") or "")
        mode_actual = str(search_payload.get("mode") or mode_norm)

        status = "OK"
        notes: list[str] = []
        if search_status == "INDEX_BUILDING":
            status = "WARN"
            notes.append("index_building_in_progress")
        elif search_status not in {"OK", ""}:
            status = "WARN"
            notes.append(f"search_status={search_status}")

        cap_status = str(capabilities.get("status") or "").strip().upper()
        if cap_status and cap_status != "OK":
            status = "WARN"
            notes.append(f"capabilities_status={cap_status}")

        result: dict[str, Any] = {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": status,
            "scope": scope_norm,
            "query": query_norm,
            "mode_requested": mode_norm,
            "mode_actual": mode_actual,
            "search_status": search_status or "OK",
            "engine": engine,
            "hits": _safe_int(hits, 0),
            "duration_ms": _safe_int(duration_ms, 0),
            "capabilities_summary": {
                "contract_id": str(capabilities.get("contract_id") or ""),
                "auto_mode_primary": str((capabilities.get("routing") or {}).get("auto_mode_primary") or "")
                if isinstance(capabilities.get("routing"), dict)
                else "",
                "adapter_count": len(capabilities.get("adapters") or []) if isinstance(capabilities.get("adapters"), list) else 0,
            },
            "index_before": {
                "status": str(index_before.get("status") or ""),
                "adapter_id": str((index_before.get("index") or {}).get("adapter_id") or "")
                if isinstance(index_before.get("index"), dict)
                else "",
            },
            "index_after": {
                "status": str(index_after.get("status") or ""),
                "adapter_id": str((index_after.get("index") or {}).get("adapter_id") or "")
                if isinstance(index_after.get("index"), dict)
                else "",
            },
            "notes": notes,
        }
    except Exception as exc:
        result = {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(workspace_root),
            "status": "FAIL",
            "error_code": "SEARCH_CHECK_RUNTIME_ERROR",
            "detail": str(exc),
            "scope": scope_norm,
            "query": query_norm,
            "mode_requested": mode_norm,
            "notes": ["search_check_failed"],
        }

    result["report_path"] = _rel_from_workspace(out_json, workspace_root)
    result["report_md_path"] = _rel_from_workspace(out_md, workspace_root)
    result["evidence_paths"] = sorted(
        {
            str(result["report_path"]),
            str(result["report_md_path"]),
            str(Path(".cache") / "index" / "keyword_index_manifest.v1.json"),
            str(Path(".cache") / "state" / "keyword_search"),
        }
    )

    out_json.write_text(_dump_json(result), encoding="utf-8")
    out_md.write_text(_build_markdown(result), encoding="utf-8")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: search-check; user_command=false")
        print(f"workspace_root={workspace_root}")
        print("RESULT:")
        print(f"status={result.get('status')}")
        print(f"scope={result.get('scope')}")
        print(f"query={result.get('query')}")
        print(f"mode={result.get('mode_actual') or result.get('mode_requested')}")
        print(f"engine={result.get('engine', '')}")
        print(f"hits={result.get('hits', 0)}")
        print(f"duration_ms={result.get('duration_ms', 0)}")
        print("EVIDENCE:")
        print(str(result.get("report_path") or ""))
        print(str(result.get("report_md_path") or ""))
        print("ACTIONS:")
        print("search-check")
        print("extension-run")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result

