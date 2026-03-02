from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"north_star_matrix_builder_contract_test failed: {message}")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _find_row(payload: dict, *, criterion_id: str, subtheme_id: str) -> dict:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("criterion_id") or "") != criterion_id:
            continue
        if str(item.get("subtheme_id") or "") != subtheme_id:
            continue
        return item
    return {}


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.benchmark.north_star_matrix_builder import build_north_star_stage_matrices

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        index_dir = ws / ".cache" / "index"

        _write_json(
            index_dir / "trend_catalog.v1.json",
            {
                "version": "v1",
                "items": [
                    {
                        "id": "REF-001",
                        "title": "Reference item",
                        "topic": "quality_axis",
                        "subject_id": "subject_alpha",
                        "theme_id": "theme_alpha",
                        "theme_title_tr": "Tema Alfa",
                        "subtheme_id": "subtheme_alpha",
                        "subtheme_title_tr": "Alt Tema Alfa",
                        "match_status": "TRIGGERED",
                        "catalog": "TREND",
                    }
                ],
            },
        )
        _write_json(index_dir / "bp_catalog.v1.json", {"version": "v1", "items": []})
        _write_json(
            index_dir / "assessment_eval.v1.json",
            {
                "version": "v1",
                "lenses": {
                    "lens_alpha": {
                        "findings": {
                            "items": [
                                {
                                    "id": "ASS-001",
                                    "title": "Assessment item",
                                    "topic": "quality_axis",
                                    "subject_id": "subject_alpha",
                                    "theme_id": "theme_alpha",
                                    "theme_title_tr": "Tema Alfa",
                                    "subtheme_id": "subtheme_alpha",
                                    "subtheme_title_tr": "Alt Tema Alfa",
                                    "match_status": "TRIGGERED",
                                    "catalog": "LENS",
                                },
                                {
                                    "id": "GAP-001",
                                    "title": "Gap item",
                                    "topic": "quality_axis",
                                    "subject_id": "subject_alpha",
                                    "theme_id": "theme_alpha",
                                    "theme_title_tr": "Tema Alfa",
                                    "subtheme_id": "subtheme_alpha",
                                    "subtheme_title_tr": "Alt Tema Alfa",
                                    "match_status": "NOT_TRIGGERED",
                                    "catalog": "LENS",
                                },
                            ]
                        }
                    }
                },
            },
        )
        _write_json(
            index_dir / "gap_register.v1.json",
            {
                "version": "v1",
                "gaps": [
                    {
                        "id": "REGISTER-GAP-001",
                        "title": "Unmapped gap signal",
                    }
                ],
            },
        )
        _write_json(
            index_dir / "mechanisms.registry.v1.json",
            {
                "version": "v1",
                "subjects": [
                    {
                        "subject_id": "subject_alpha",
                        "subject_title_tr": "Konu Alfa",
                        "status": "ACTIVE",
                        "themes": [
                            {
                                "theme_id": "theme_alpha",
                                "title_tr": "Tema Alfa",
                                "subthemes": [
                                    {
                                        "subtheme_id": "subtheme_alpha",
                                        "title_tr": "Alt Tema Alfa",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        )
        _write_json(
            ws / "docs" / "OPERATIONS" / "north_star_criteria_packs.v1.json",
            {
                "version": "v1",
                "core_8": ["quality_axis"],
                "axis_registry": [
                    {
                        "axis_id": "quality_axis",
                        "label_tr": "Kalite Eksen",
                        "label_en": "Quality Axis",
                    }
                ],
                "perspective_packs": {
                    "BUSINESS_PROCESS": {
                        "criteria": [],
                    }
                },
            },
        )

        matrices = build_north_star_stage_matrices(workspace_root=ws, core_root=repo_root)
        _must(isinstance(matrices, dict), "matrices must be dict")
        for stage in ("reference", "assessment", "gap"):
            _must(stage in matrices, f"{stage} stage missing")
            payload = matrices.get(stage)
            _must(isinstance(payload, dict), f"{stage} payload must be dict")
            _must(str(payload.get("stage") or "") == stage, f"{stage} stage value mismatch")
            _must(isinstance(payload.get("items"), list), f"{stage}.items must be list")

        reference_row = _find_row(matrices["reference"], criterion_id="quality_axis", subtheme_id="subtheme_alpha")
        assessment_row = _find_row(matrices["assessment"], criterion_id="quality_axis", subtheme_id="subtheme_alpha")
        gap_row = _find_row(matrices["gap"], criterion_id="quality_axis", subtheme_id="subtheme_alpha")

        _must(bool(reference_row), "reference row not found")
        _must(bool(assessment_row), "assessment row not found")
        _must(bool(gap_row), "gap row not found")

        _must(int(reference_row.get("item_count") or 0) >= 1, "reference item_count must be >= 1")
        _must(int(assessment_row.get("item_count") or 0) >= 1, "assessment item_count must be >= 1")
        _must(int(gap_row.get("item_count") or 0) >= 1, "gap item_count must be >= 1")
        _must(str(gap_row.get("status") or "") == "OPEN", "gap row status must be OPEN")

        gap_summary = matrices["gap"].get("summary") if isinstance(matrices["gap"], dict) else {}
        _must(int((gap_summary or {}).get("gap_register_items_total") or 0) == 1, "gap_register total mismatch")
        _must(int((gap_summary or {}).get("gap_register_items_unmapped") or 0) == 1, "gap_register unmapped mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
