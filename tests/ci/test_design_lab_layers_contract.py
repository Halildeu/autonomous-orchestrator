"""Contract tests for design lab layer catalog and CI gate."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Schema & Registry existence
# ---------------------------------------------------------------------------

def test_design_lab_layer_schema_exists() -> None:
    path = REPO_ROOT / "schemas" / "design-lab-layer.schema.v1.json"
    assert path.exists()
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert schema["title"] == "Design Lab Layer Catalog"
    assert "foundation" in str(schema)


def test_design_lab_registry_exists() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["kind"] == "design-lab-layer-catalog"
    assert data["status"] == "ACTIVE"


def test_registry_has_4_layers() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    layers = data["layers"]
    assert len(layers) == 4
    ids = [l["layer_id"] for l in layers]
    assert ids == ["foundation", "component", "recipe", "page"]


def test_layer_order_matches() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for i, layer in enumerate(data["layers"]):
        assert layer["order"] == i


def test_dependency_rules_are_bottom_up() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = data["dependency_rules"]["allowed_imports"]
    # foundation imports nothing
    assert allowed["foundation"] == []
    # component only imports foundation
    assert allowed["component"] == ["foundation"]
    # recipe imports component + foundation
    assert set(allowed["recipe"]) == {"component", "foundation"}
    # page imports all lower
    assert set(allowed["page"]) == {"recipe", "component", "foundation"}


def test_each_layer_has_items() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for layer in data["layers"]:
        assert len(layer["items"]) > 0, f"{layer['layer_id']} has no items"


def test_no_duplicate_item_ids() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    all_ids = []
    for layer in data["layers"]:
        for item in layer["items"]:
            all_ids.append(item["item_id"])
    assert len(all_ids) == len(set(all_ids)), f"Duplicate item IDs found"


def test_bilingual_display_names() -> None:
    path = REPO_ROOT / "registry" / "design_lab_layers.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for layer in data["layers"]:
        assert "tr" in layer["display_name"]
        assert "en" in layer["display_name"]
        assert "tr" in layer["description"]
        assert "en" in layer["description"]


# ---------------------------------------------------------------------------
# CI Gate
# ---------------------------------------------------------------------------

def test_ci_gate_passes_on_valid_catalog() -> None:
    from ci.check_design_lab_layers import check_design_lab_layers
    result = check_design_lab_layers(repo_root=REPO_ROOT)
    assert result["status"] == "OK", f"Violations: {result.get('violations')}"
    assert result["summary"]["total_layers"] == 4
    assert result["summary"]["total_items"] > 0


def test_ci_gate_fails_on_missing_catalog() -> None:
    from ci.check_design_lab_layers import check_design_lab_layers
    with tempfile.TemporaryDirectory() as tmp:
        result = check_design_lab_layers(repo_root=Path(tmp))
    assert result["status"] == "FAIL"
    assert result["error"] == "CATALOG_MISSING"


def test_ci_gate_detects_upward_import() -> None:
    """Verify detection of an invalid upward dependency."""
    from ci.check_design_lab_layers import check_design_lab_layers

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "registry").mkdir()
        bad_catalog = {
            "version": "v1",
            "kind": "design-lab-layer-catalog",
            "status": "ACTIVE",
            "layers": [
                {"layer_id": "foundation", "order": 0,
                 "display_name": {"tr": "T", "en": "F"}, "description": {"tr": "T", "en": "F"},
                 "path_pattern": "a/**", "export_convention": "x",
                 "items": [{"item_id": "tok", "name": "Token", "status": "stable"}]},
                {"layer_id": "component", "order": 1,
                 "display_name": {"tr": "T", "en": "C"}, "description": {"tr": "T", "en": "C"},
                 "path_pattern": "b/**", "export_convention": "x",
                 "items": [{"item_id": "btn", "name": "Button", "status": "stable", "depends_on": ["tok"]}]},
                {"layer_id": "recipe", "order": 2,
                 "display_name": {"tr": "T", "en": "R"}, "description": {"tr": "T", "en": "R"},
                 "path_pattern": "c/**", "export_convention": "x",
                 "items": [{"item_id": "rec", "name": "Recipe", "status": "stable", "depends_on": ["btn"]}]},
                {"layer_id": "page", "order": 3,
                 "display_name": {"tr": "T", "en": "P"}, "description": {"tr": "T", "en": "P"},
                 "path_pattern": "d/**", "export_convention": "x",
                 "items": [{"item_id": "pg", "name": "Page", "status": "stable", "depends_on": ["rec"]}]},
            ],
            "dependency_rules": {
                "allowed_imports": {
                    "foundation": ["component"],
                    "component": ["foundation"],
                    "recipe": ["component", "foundation"],
                    "page": ["recipe", "component", "foundation"],
                },
            },
        }
        (tmp_root / "registry" / "design_lab_layers.v1.json").write_text(
            json.dumps(bad_catalog), encoding="utf-8"
        )
        result = check_design_lab_layers(repo_root=tmp_root)
        assert result["status"] == "FAIL"
        upward = [v for v in result["violations"] if v["rule"] == "UPWARD_IMPORT_IN_RULES"]
        assert len(upward) > 0


# ---------------------------------------------------------------------------
# Policy integration
# ---------------------------------------------------------------------------

def test_policy_has_design_lab_layers() -> None:
    path = REPO_ROOT / "policies" / "policy_ui_design_system.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    dll = data["design_lab_layers"]
    assert dll["catalog_path"] == "registry/design_lab_layers.v1.json"
    assert dll["layer_order"] == ["foundation", "component", "recipe", "page"]
    assert dll["enforcement"]["import_direction"] == "bottom-up-only"
    assert dll["enforcement"]["recipe_no_direct_foundation"] is True
    assert dll["enforcement"]["page_requires_layout_wrapper"] is True


def test_policy_schema_accepts_design_lab_layers() -> None:
    path = REPO_ROOT / "schemas" / "policy-ui-design-system.schema.v1.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert "design_lab_layers" in schema["required"]
    assert "design_lab_layers" in schema["properties"]
