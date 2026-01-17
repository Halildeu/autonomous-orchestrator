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

    tmp_root = repo_root / ".tmp_docs_drift_legacy_exclude"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    docs_dir = tmp_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = docs_dir / "legacy_redirect.md"
    legacy_path.write_text("Legacy Redirect\n# Legacy\n", encoding="utf-8")
    archive_only_path = docs_dir / "archive_only.md"
    archive_only_path.write_text("ARCHIVE ONLY\n# Archive\n", encoding="utf-8")

    mapping = dict(DOCS_DRIFT_DEFAULT_MAPPING)
    mapping["view_doc_allowlist_globs"] = list(DOCS_DRIFT_DEFAULT_MAPPING["view_doc_allowlist_globs"])
    signal = compute_docs_drift_signal(core_root=tmp_root, mapping=mapping)
    if signal.get("unmapped_md_count") != 0:
        raise SystemExit("operability_docs_drift_legacy_exclude_contract_test failed: unmapped_md_count not 0")
    mapped_sources = signal.get("mapped_sources") if isinstance(signal, dict) else {}
    if int(mapped_sources.get("excluded_legacy_count", 0) or 0) < 2:
        raise SystemExit(
            "operability_docs_drift_legacy_exclude_contract_test failed: legacy exclusions not counted"
        )

    shutil.rmtree(tmp_root)
    print(json.dumps({"status": "OK", "signal": signal}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
