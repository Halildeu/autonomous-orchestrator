from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import DOCS_DRIFT_DEFAULT_MAPPING, compute_docs_drift_signal

    tmp_root = repo_root / ".tmp_docs_drift_workspace_allowlist"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    (tmp_root / ".gemini").mkdir(parents=True, exist_ok=True)
    (tmp_root / "tenant" / "TENANT-DEFAULT").mkdir(parents=True, exist_ok=True)
    (tmp_root / "extensions" / "PRJ-TEST").mkdir(parents=True, exist_ok=True)
    (tmp_root / "docs" / "OPERATIONS").mkdir(parents=True, exist_ok=True)
    (tmp_root / "AGENTS.md").write_text("# Router\n- docs/OPERATIONS/SSOT-MAP.md\n", encoding="utf-8")
    (tmp_root / "docs" / "OPERATIONS" / "SSOT-MAP.md").write_text("# Map\n- AGENTS.md\n", encoding="utf-8")
    (tmp_root / ".gemini" / "INSTRUCTIONS.md").write_text("# Gemini\n", encoding="utf-8")
    (tmp_root / "tenant" / "TENANT-DEFAULT" / "context.v1.md").write_text("# Tenant\n", encoding="utf-8")
    (tmp_root / "extensions" / "PRJ-TEST" / "README.md").write_text("# Extension\n", encoding="utf-8")

    mapping = dict(DOCS_DRIFT_DEFAULT_MAPPING)
    mapping["view_doc_allowlist_globs"] = list(DOCS_DRIFT_DEFAULT_MAPPING["view_doc_allowlist_globs"])
    signal = compute_docs_drift_signal(core_root=tmp_root, mapping=mapping)
    if signal.get("unmapped_md_count") != 0:
        raise SystemExit("operability_docs_drift_workspace_allowlist_contract_test failed: unmapped markdown remains")

    shutil.rmtree(tmp_root)
    print(json.dumps({"status": "OK", "signal": signal}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
