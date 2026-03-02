from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    manifest_path = Path(__file__).resolve().parents[1] / "extension.manifest.v1.json"
    schema_path = repo_root / "schemas" / "extension-manifest.schema.v1.json"

    manifest = _load_json(manifest_path)
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(manifest)

    docs_ref = str(manifest.get("docs_ref") or "")
    if not docs_ref:
        raise SystemExit("contract_test failed: docs_ref missing")
    docs_path = docs_ref.split("#", 1)[0]
    if docs_path and not (repo_root / docs_path).exists():
        raise SystemExit("contract_test failed: docs_ref path missing")

    ai_context_refs = manifest.get("ai_context_refs")
    if not isinstance(ai_context_refs, list) or not ai_context_refs:
        raise SystemExit("contract_test failed: ai_context_refs missing")
    for ref in ai_context_refs:
        if not isinstance(ref, str) or not ref.strip():
            raise SystemExit("contract_test failed: ai_context_refs invalid")
        if not (repo_root / ref).exists():
            raise SystemExit("contract_test failed: ai_context_refs path missing")

    print(json.dumps({"status": "OK", "extension_id": manifest.get("extension_id")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
