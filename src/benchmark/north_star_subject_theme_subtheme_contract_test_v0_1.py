from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_tag_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if s:
            out.append(s)
    return sorted(set(out))


def _extract_subject_id(tags: list[str]) -> str:
    for tag in tags:
        if tag.lower().startswith("subject:"):
            return tag.split(":", 1)[1].strip()
    return ""


def _validate_subject_theme_subtheme_items(
    *, items: list[dict], ethics_taxonomy: dict | None
) -> list[str]:
    errors: list[str] = []
    ethics_theme_ids: set[str] = set()
    ethics_subtheme_to_theme: dict[str, str] = {}

    if ethics_taxonomy and isinstance(ethics_taxonomy, dict):
        for theme in ethics_taxonomy.get("themes", []) if isinstance(ethics_taxonomy.get("themes"), list) else []:
            if not isinstance(theme, dict):
                continue
            tid = str(theme.get("theme_id") or "").strip()
            if tid:
                ethics_theme_ids.add(tid)
        for sub in ethics_taxonomy.get("subthemes", []) if isinstance(ethics_taxonomy.get("subthemes"), list) else []:
            if not isinstance(sub, dict):
                continue
            sid = str(sub.get("subtheme_id") or "").strip()
            tid = str(sub.get("theme_id") or "").strip()
            if sid and tid:
                ethics_subtheme_to_theme[sid] = tid

    for item in items:
        if not isinstance(item, dict):
            continue
        tags = _normalize_tag_list(item.get("tags"))
        subject_id = _extract_subject_id(tags)
        if not subject_id:
            continue

        item_id = str(item.get("id") or "").strip() or "(missing id)"
        theme_id = str(item.get("theme_id") or "").strip()
        theme_title_tr = str(item.get("theme_title_tr") or "").strip()
        subtheme_id = str(item.get("subtheme_id") or "").strip()
        subtheme_title_tr = str(item.get("subtheme_title_tr") or "").strip()

        if not theme_id:
            errors.append(f"{item_id}: subject:{subject_id} requires theme_id")
        if not theme_title_tr:
            errors.append(f"{item_id}: subject:{subject_id} requires theme_title_tr")
        if not subtheme_id:
            errors.append(f"{item_id}: subject:{subject_id} requires subtheme_id")
        if not subtheme_title_tr:
            errors.append(f"{item_id}: subject:{subject_id} requires subtheme_title_tr")

        if subject_id == "ethics" and theme_id and ethics_theme_ids and theme_id not in ethics_theme_ids:
            errors.append(f"{item_id}: ethics theme_id unknown: {theme_id}")

        if subject_id == "ethics" and theme_id and subtheme_id:
            expected_theme = ethics_subtheme_to_theme.get(subtheme_id)
            if expected_theme and expected_theme != theme_id:
                errors.append(
                    f"{item_id}: ethics subtheme_id {subtheme_id} expected theme_id {expected_theme} (got {theme_id})"
                )

    return sorted(set(errors))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    taxonomy_path = repo_root / "docs" / "OPERATIONS" / "north_star_ethics_taxonomy.v1.json"
    ethics_taxonomy = _load_json(taxonomy_path) if taxonomy_path.exists() else None
    _assert(bool(ethics_taxonomy), f"Missing ethics taxonomy file: {taxonomy_path}")

    invalid_items = [
        {
            "id": "ethics-bp-001",
            "title": "Ethics item (invalid: missing theme/subtheme)",
            "source": "seed",
            "tags": ["subject:ethics", "topic:uygunluk_risk_guvence_kontrol"],
        }
    ]
    invalid_errors = _validate_subject_theme_subtheme_items(items=invalid_items, ethics_taxonomy=ethics_taxonomy)
    _assert(
        any("requires theme_id" in e for e in invalid_errors),
        f"Expected invalid items to fail theme/subtheme requirements, got: {invalid_errors}",
    )

    valid_items = [
        {
            "id": "ethics-bp-002",
            "title": "COI guardrail enforced",
            "source": "seed",
            "tags": ["subject:ethics", "topic:uygunluk_risk_guvence_kontrol"],
            "theme_id": "triage",
            "theme_title_tr": "Triage",
            "subtheme_id": "coi",
            "subtheme_title_tr": "Çıkar çatışması (COI)",
        }
    ]
    valid_errors = _validate_subject_theme_subtheme_items(items=valid_items, ethics_taxonomy=ethics_taxonomy)
    _assert(not valid_errors, f"Expected valid items to pass theme/subtheme requirements, got: {valid_errors}")

    # Optional: validate the current default workspace catalogs if present.
    ws_root = repo_root / ".cache" / "ws_customer_default"
    ws_catalogs = [
        ws_root / ".cache" / "index" / "bp_catalog.v1.json",
        ws_root / ".cache" / "index" / "trend_catalog.v1.json",
    ]
    for cat_path in ws_catalogs:
        if not cat_path.exists():
            continue
        obj = _load_json(cat_path)
        items = obj.get("items") if isinstance(obj, dict) else None
        items_list = items if isinstance(items, list) else []
        errs = _validate_subject_theme_subtheme_items(items=items_list, ethics_taxonomy=ethics_taxonomy)
        _assert(not errs, f"{cat_path}: subject theme/subtheme contract failed: {errs[:12]}")

    print("OK")


if __name__ == "__main__":
    main()

