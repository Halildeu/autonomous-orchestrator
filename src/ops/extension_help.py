from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = [str(v) for v in value if isinstance(v, str) and v]
    return sorted(set(cleaned))


def _entrypoints_from_manifest(manifest: dict[str, Any]) -> dict[str, list[str]]:
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    return {
        "ops": _list_str(entrypoints.get("ops")),
        "ops_single_gate": _list_str(entrypoints.get("ops_single_gate")),
        "kernel_api_actions": _list_str(entrypoints.get("kernel_api_actions")),
        "cockpit_sections": _list_str(entrypoints.get("cockpit_sections")),
    }


def _tests_entrypoints_from_manifest(manifest: dict[str, Any]) -> list[str]:
    tests_entrypoints = _list_str(manifest.get("tests_entrypoints"))
    if tests_entrypoints:
        return tests_entrypoints
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    return _list_str(entrypoints.get("tests"))


def _load_manifest(repo_root: Path, manifest_path: str) -> tuple[dict[str, Any] | None, str | None]:
    path = repo_root / manifest_path
    if not path.exists():
        return (None, "manifest_missing")
    try:
        obj = _load_json(path)
    except Exception:
        return (None, "manifest_invalid_json")
    if not isinstance(obj, dict):
        return (None, "manifest_invalid_object")
    return (obj, None)


def build_extension_help(*, workspace_root: Path, detail: bool = False) -> dict[str, Any]:
    from src.ops.extension_registry import build_extension_registry

    build_extension_registry(workspace_root=workspace_root, mode="report")

    registry_path = workspace_root / ".cache" / "index" / "extension_registry.v1.json"
    status = "OK"
    errors: list[str] = []
    notes: list[str] = []
    extensions: list[dict[str, Any]] = []
    with_tests_entrypoints = 0
    with_tests_files = 0

    if not registry_path.exists():
        status = "IDLE"
        errors.append("extension_registry_missing")
    else:
        try:
            registry = _load_json(registry_path)
        except Exception:
            registry = {}
            status = "WARN"
            errors.append("extension_registry_invalid")
        entries = registry.get("extensions") if isinstance(registry, dict) else None
        entries = [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []

        repo_root = _repo_root()
        for entry in sorted(entries, key=lambda e: str(e.get("extension_id") or "")):
            ext_id = entry.get("extension_id") if isinstance(entry.get("extension_id"), str) else ""
            semver = entry.get("semver") if isinstance(entry.get("semver"), str) else ""
            manifest_path = entry.get("manifest_path") if isinstance(entry.get("manifest_path"), str) else ""
            if not ext_id or not manifest_path:
                continue
            manifest, err = _load_manifest(repo_root, manifest_path)
            if err:
                errors.append(f"{manifest_path}:{err}")
                continue
            docs_ref = manifest.get("docs_ref") if isinstance(manifest.get("docs_ref"), str) else ""
            ai_context_refs = _list_str(manifest.get("ai_context_refs"))
            outputs_obj = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}
            policy_files = _list_str(manifest.get("policy_files"))
            policy_files.extend(_list_str(manifest.get("policies")))
            policy_files = sorted(set(policy_files))
            gates_obj = manifest.get("gates") if isinstance(manifest.get("gates"), dict) else {}
            gates_required = _list_str(gates_obj.get("required"))
            tests_entrypoints = _tests_entrypoints_from_manifest(manifest)
            if tests_entrypoints:
                with_tests_entrypoints += 1
                ext_root = (repo_root / manifest_path).parent
                tests_ok = True
                for p in tests_entrypoints:
                    path_obj = repo_root / p
                    if not path_obj.exists():
                        tests_ok = False
                        break
                    if not str(p).startswith(str(ext_root.relative_to(repo_root)).replace("\\\\", "/") + "/tests/"):
                        tests_ok = False
                        break
                if tests_ok:
                    with_tests_files += 1

            outputs = {
                "workspace_reports": _list_str(outputs_obj.get("workspace_reports")),
            }
            item = {
                "extension_id": ext_id,
                "semver": semver,
                "manifest_path": manifest_path,
                "docs_ref": docs_ref,
                "ai_context_refs": ai_context_refs,
                "entrypoints": _entrypoints_from_manifest(manifest),
                "outputs": outputs,
                "policy_files": policy_files,
                "gates_required": gates_required,
            }
            if detail:
                item["notes"] = _list_str(manifest.get("notes"))
            extensions.append(item)

    docs_total = len(extensions)
    with_docs = len([e for e in extensions if isinstance(e.get("docs_ref"), str) and e.get("docs_ref")])
    with_ai = len([e for e in extensions if isinstance(e.get("ai_context_refs"), list) and e.get("ai_context_refs")])
    docs_coverage = {"total": docs_total, "with_docs_ref": with_docs, "with_ai_context_refs": with_ai}
    tests_coverage = {
        "total": docs_total,
        "with_tests_entrypoints": with_tests_entrypoints,
        "with_tests_files": with_tests_files,
    }

    if docs_total == 0 and status == "OK":
        status = "IDLE"
        notes.append("extensions_empty")
    if errors and status != "FAIL":
        status = "WARN"

    payload = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "status": status,
        "docs_coverage": docs_coverage,
        "tests_coverage": tests_coverage,
        "extensions": extensions,
        "notes": notes,
        "errors": errors,
    }

    out_json = workspace_root / ".cache" / "reports" / "extension_help.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "extension_help.v1.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(_dump_json(payload), encoding="utf-8")

    md_lines = [
        "# Extension Help (v1)",
        "",
        f"Status: {status}",
        f"Total: {docs_total}",
        f"Docs coverage: {with_docs}/{docs_total}",
        f"AI context coverage: {with_ai}/{docs_total}",
        f"Tests coverage: {with_tests_files}/{docs_total}",
        "",
        f"Report: {out_json.relative_to(workspace_root)}",
    ]
    if extensions:
        md_lines.append("")
        md_lines.append("## Extensions")
        for ext in extensions[:10]:
            md_lines.append(f"- {ext.get('extension_id')} {ext.get('semver')}")
    if errors:
        md_lines.append("")
        md_lines.append("## Errors")
        for err in errors[:10]:
            md_lines.append(f"- {err}")

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "status": status,
        "report_path": str(out_json.relative_to(workspace_root)),
        "summary_path": str(out_md.relative_to(workspace_root)),
        "docs_coverage": docs_coverage,
        "tests_coverage": tests_coverage,
        "count_total": docs_total,
        "errors": errors,
    }


def run_extension_help(*, workspace_root: Path, detail: bool, chat: bool) -> dict[str, Any]:
    result = build_extension_help(workspace_root=workspace_root, detail=detail)
    status = result.get("status") if isinstance(result, dict) else "WARN"

    if chat:
        preview_lines = [
            "PROGRAM-LED: extension-help; user_command=false",
            f"workspace_root={workspace_root}",
            f"detail={detail}",
        ]
        result_lines = [
            f"status={status}",
            f"count_total={result.get('count_total', 0)}",
            f"docs_coverage={result.get('docs_coverage', {})}",
            f"tests_coverage={result.get('tests_coverage', {})}",
        ]
        evidence_lines = [
            f"extension_help={result.get('report_path')}",
            f"summary={result.get('summary_path')}",
        ]
        actions_line = "no_actions"
        next_lines = ["Devam et", "Durumu goster", "Duraklat"]

        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join([str(x) for x in result_lines if x]))
        print("EVIDENCE:")
        print("\n".join([str(x) for x in evidence_lines if x]))
        print("ACTIONS:")
        print(actions_line)
        print("NEXT:")
        print("\n".join(next_lines))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))

    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.extension_help")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--detail", default="false", help="true|false (default: false)")
    ap.add_argument("--chat", default="false", help="true|false (default: false)")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    detail = str(args.detail).strip().lower() in {"1", "true", "yes", "y", "on"}
    chat = str(args.chat).strip().lower() in {"1", "true", "yes", "y", "on"}

    res = run_extension_help(workspace_root=workspace_root, detail=detail, chat=chat)
    return 0 if res.get("status") in {"OK", "WARN", "IDLE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
