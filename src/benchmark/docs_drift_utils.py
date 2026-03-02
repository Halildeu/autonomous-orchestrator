from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DOCS_DRIFT_DEFAULT_VIEW_ALLOWLIST = [
    "docs/ARCHITECTURE/**/*.md",
    "docs/DECISIONS/**/*.md",
    "docs/OPERATIONS/**/*.md",
    "fixtures/**/*.md",
    "modules/**/README.md",
    "roadmaps/PROJECTS/**/*.md",
    "templates/**/*.md",
]

DOCS_DRIFT_DEFAULT_MAPPING = {
    "include_extension_manifest_refs": True,
    "view_doc_allowlist_globs": DOCS_DRIFT_DEFAULT_VIEW_ALLOWLIST,
    "exclude_legacy_redirect_stubs": True,
    "exclude_archive_only_banners": True,
    "root_readme_mode": "mapped",
    "root_changelog_mode": "mapped",
}

DOCS_DRIFT_EXCLUDE_DIRS = {".cache", "evidence", ".codex", ".venv", ".git"}
DOCS_DRIFT_LEGACY_MARKERS = ("Legacy Redirect", "ARCHIVE ONLY")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_md_paths(root: Path, *, exclude_dirs: set[str]) -> list[Path]:
    if not root.exists():
        return []
    paths: list[Path] = []
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def _collect_extension_manifest_paths(core_root: Path) -> list[Path]:
    ext_root = core_root / "extensions"
    if not ext_root.exists():
        return []
    return sorted(ext_root.rglob("extension.manifest*.json"))


def _extract_md_links(*, text: str, core_root: Path) -> set[str]:
    md_pattern = re.compile(r"([A-Za-z0-9_./-]+\.md)")
    hits: set[str] = set()
    core_root = core_root.resolve()
    for match in md_pattern.findall(text or ""):
        token = match.strip()
        if token.startswith("./"):
            token = token[2:]
        if token.startswith("/"):
            token = token[1:]
        if not token:
            continue
        rel = Path(token).as_posix()
        candidate = (core_root / rel).resolve()
        try:
            candidate.relative_to(core_root)
        except Exception:
            continue
        if candidate.exists() and candidate.is_file():
            hits.add(candidate.relative_to(core_root).as_posix())
    return hits


def _resolve_manifest_ref(*, core_root: Path, manifest_path: Path, ref: str) -> str | None:
    if not isinstance(ref, str) or not ref.strip():
        return None
    ref_path = Path(ref)
    candidates: list[Path] = []
    if ref_path.is_absolute():
        candidates.append(ref_path)
    else:
        candidates.append((core_root / ref_path).resolve())
        candidates.append((manifest_path.parent / ref_path).resolve())
    core_root = core_root.resolve()
    for candidate in candidates:
        try:
            candidate.relative_to(core_root)
        except Exception:
            continue
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".md":
            return candidate.relative_to(core_root).as_posix()
    return None


def _collect_extension_manifest_refs(*, core_root: Path, manifest_paths: list[Path]) -> set[str]:
    refs: set[str] = set()
    for manifest_path in manifest_paths:
        try:
            obj = _load_json(manifest_path)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        doc_ref = obj.get("docs_ref")
        if isinstance(doc_ref, str):
            resolved = _resolve_manifest_ref(core_root=core_root, manifest_path=manifest_path, ref=doc_ref)
            if resolved:
                refs.add(resolved)
        ai_refs = obj.get("ai_context_refs")
        if isinstance(ai_refs, list):
            for item in ai_refs:
                if isinstance(item, str):
                    resolved = _resolve_manifest_ref(core_root=core_root, manifest_path=manifest_path, ref=item)
                    if resolved:
                        refs.add(resolved)
    return refs


def _collect_view_allowlist(*, core_root: Path, globs: list[str]) -> set[str]:
    allowlist: set[str] = set()
    core_root = core_root.resolve()
    for pattern in globs:
        for path in core_root.glob(pattern):
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            if any(part in DOCS_DRIFT_EXCLUDE_DIRS for part in path.parts):
                continue
            try:
                rel = path.relative_to(core_root).as_posix()
            except Exception:
                continue
            allowlist.add(rel)
    return allowlist


def _is_legacy_excluded(
    *, path: Path, exclude_legacy_redirect: bool, exclude_archive_only: bool, max_lines: int = 30
) -> bool:
    if not exclude_legacy_redirect and not exclude_archive_only:
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:max_lines]
    except Exception:
        return False
    head = "\n".join(lines)
    if exclude_legacy_redirect and DOCS_DRIFT_LEGACY_MARKERS[0] in head:
        return True
    if exclude_archive_only and DOCS_DRIFT_LEGACY_MARKERS[1] in head:
        return True
    return False


def compute_docs_drift_signal(*, core_root: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    all_md_paths = _iter_md_paths(core_root, exclude_dirs=DOCS_DRIFT_EXCLUDE_DIRS)
    all_md = {p.relative_to(core_root).as_posix() for p in all_md_paths}
    archive_md = {p for p in all_md if p.startswith("docs/ARCHIVE/")}

    ssot_linked: set[str] = set()
    ssot_map_path = core_root / "docs" / "OPERATIONS" / "SSOT-MAP.md"
    agents_path = core_root / "AGENTS.md"
    if ssot_map_path.exists():
        ssot_linked |= _extract_md_links(text=ssot_map_path.read_text(encoding="utf-8"), core_root=core_root)
    if agents_path.exists():
        ssot_linked |= _extract_md_links(text=agents_path.read_text(encoding="utf-8"), core_root=core_root)

    view_globs = mapping.get("view_doc_allowlist_globs")
    view_globs = view_globs if isinstance(view_globs, list) else []
    view_allowlist = _collect_view_allowlist(core_root=core_root, globs=view_globs)

    manifest_paths = _collect_extension_manifest_paths(core_root)
    if mapping.get("include_extension_manifest_refs", True):
        manifest_refs = _collect_extension_manifest_refs(core_root=core_root, manifest_paths=manifest_paths)
    else:
        manifest_refs = set()

    root_mapped: set[str] = set()
    if mapping.get("root_readme_mode") == "mapped" and (core_root / "README.md").exists():
        root_mapped.add("README.md")
    if mapping.get("root_changelog_mode") == "mapped" and (core_root / "CHANGELOG.md").exists():
        root_mapped.add("CHANGELOG.md")

    mapped = ssot_linked | view_allowlist | manifest_refs | root_mapped

    legacy_excluded: set[str] = set()
    exclude_legacy = bool(mapping.get("exclude_legacy_redirect_stubs", True))
    exclude_archive_only = bool(mapping.get("exclude_archive_only_banners", True))
    if exclude_legacy or exclude_archive_only:
        for rel in sorted(all_md - archive_md):
            path = core_root / rel
            if _is_legacy_excluded(
                path=path,
                exclude_legacy_redirect=exclude_legacy,
                exclude_archive_only=exclude_archive_only,
            ):
                legacy_excluded.add(rel)

    unmapped = sorted(all_md - mapped - archive_md - legacy_excluded)
    return {
        "unmapped_md_count": len(unmapped),
        "unmapped_md_sample": unmapped[:20],
        "mapped_sources": {
            "ssot_router_count": len(ssot_linked),
            "extension_manifest_ref_count": len(manifest_refs),
            "view_doc_allowlist_count": len(view_allowlist),
            "excluded_legacy_count": len(legacy_excluded),
            "excluded_archive_count": len(archive_md),
        },
    }
