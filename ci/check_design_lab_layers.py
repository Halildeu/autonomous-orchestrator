#!/usr/bin/env python3
"""CI gate: validate design lab layer catalog integrity and dependency rules.

Checks:
1. Catalog exists and is valid JSON
2. All 4 layers present in correct order
3. Dependency rules are consistent (no upward imports)
4. All item depends_on references resolve to items in allowed layers
5. No duplicate item IDs across layers
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CATALOG_REL = "registry/design_lab_layers.v1.json"
LAYER_ORDER = ["foundation", "component", "recipe", "page"]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_design_lab_layers(*, repo_root: Path) -> dict[str, Any]:
    """Validate design lab layer catalog."""
    catalog_path = repo_root / CATALOG_REL
    violations: list[dict[str, Any]] = []
    warnings: list[str] = []

    # 1. Catalog exists
    if not catalog_path.exists():
        return {
            "status": "FAIL",
            "error": "CATALOG_MISSING",
            "catalog_path": str(catalog_path),
            "violations": [],
        }

    try:
        catalog = _load_json(catalog_path)
    except Exception as e:
        return {
            "status": "FAIL",
            "error": "CATALOG_INVALID_JSON",
            "detail": str(e),
            "violations": [],
        }

    # 2. Layer order
    layers = catalog.get("layers", [])
    layer_ids = [l.get("layer_id") for l in layers if isinstance(l, dict)]
    if layer_ids != LAYER_ORDER:
        violations.append({
            "rule": "LAYER_ORDER",
            "expected": LAYER_ORDER,
            "actual": layer_ids,
        })

    # Build item index: item_id → layer_id
    item_index: dict[str, str] = {}
    all_item_ids: list[str] = []

    for layer in layers:
        if not isinstance(layer, dict):
            continue
        lid = layer.get("layer_id", "")
        items = layer.get("items", [])
        for item in items:
            if not isinstance(item, dict):
                continue
            iid = item.get("item_id", "")
            if iid in item_index:
                violations.append({
                    "rule": "DUPLICATE_ITEM",
                    "item_id": iid,
                    "layers": [item_index[iid], lid],
                })
            item_index[iid] = lid
            all_item_ids.append(iid)

    # 3. Dependency rules — check allowed_imports
    dep_rules = catalog.get("dependency_rules", {})
    allowed = dep_rules.get("allowed_imports", {})

    for lid in LAYER_ORDER:
        allowed_layers = allowed.get(lid, [])
        layer_idx = LAYER_ORDER.index(lid)
        for al in allowed_layers:
            if al in LAYER_ORDER:
                al_idx = LAYER_ORDER.index(al)
                if al_idx >= layer_idx:
                    violations.append({
                        "rule": "UPWARD_IMPORT_IN_RULES",
                        "layer": lid,
                        "imports_from": al,
                        "reason": f"{lid} (order={layer_idx}) cannot import from {al} (order={al_idx})",
                    })

    # 4. Item depends_on references
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        lid = layer.get("layer_id", "")
        layer_idx = LAYER_ORDER.index(lid) if lid in LAYER_ORDER else -1
        allowed_layers_for_lid = set(allowed.get(lid, []))

        for item in layer.get("items", []):
            if not isinstance(item, dict):
                continue
            iid = item.get("item_id", "")
            deps = item.get("depends_on", [])
            for dep in deps:
                if dep not in item_index:
                    warnings.append(f"{lid}/{iid} depends_on '{dep}' not found in catalog")
                    continue
                dep_layer = item_index[dep]
                if dep_layer not in allowed_layers_for_lid and dep_layer != lid:
                    violations.append({
                        "rule": "FORBIDDEN_DEPENDENCY",
                        "item": f"{lid}/{iid}",
                        "depends_on": f"{dep_layer}/{dep}",
                        "reason": f"{lid} cannot import from {dep_layer}",
                    })

    # 5. Summary
    summary = {
        "total_layers": len(layers),
        "total_items": len(all_item_ids),
        "items_per_layer": {},
    }
    for layer in layers:
        if isinstance(layer, dict):
            lid = layer.get("layer_id", "")
            summary["items_per_layer"][lid] = len(layer.get("items", []))

    status = "FAIL" if violations else "OK"
    result: dict[str, Any] = {
        "status": status,
        "summary": summary,
        "violations": violations,
    }
    if warnings:
        result["warnings"] = warnings
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check design lab layer catalog")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    result = check_design_lab_layers(repo_root=repo_root)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
