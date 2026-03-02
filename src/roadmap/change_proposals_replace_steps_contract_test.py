from __future__ import annotations

import json
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())

    import sys

    sys.path.insert(0, str(repo_root))

    from src.roadmap.change_proposals import apply_change_to_roadmap_obj

    roadmap_obj = {
        "version": "v1",
        "project_id": "default",
        "milestones": [
            {
                "id": "M0",
                "title": "M0",
                "steps": [{"type": "note", "text": "placeholder"}],
            }
        ],
    }

    change_obj = {
        "type": "modify",
        "target": {"milestone_id": "M0"},
        "patches": [
            {
                "op": "replace_milestone_steps",
                "milestone_id": "M0",
                "steps": [
                    {"type": "note", "text": "M0 updated"},
                    {"type": "assert_core_paths_exist", "paths": ["schemas/roadmap.schema.json"]},
                ],
            }
        ],
    }

    updated = apply_change_to_roadmap_obj(roadmap_obj=roadmap_obj, change_obj=change_obj)
    ms = updated.get("milestones")[0]
    steps = ms.get("steps") if isinstance(ms, dict) else None
    if not isinstance(steps, list) or len(steps) != 2:
        raise SystemExit("change_proposals_replace_steps_contract_test failed: steps length mismatch")
    if str(steps[1].get("type") or "") != "assert_core_paths_exist":
        raise SystemExit("change_proposals_replace_steps_contract_test failed: executable step missing")

    bad_change = {
        "type": "modify",
        "target": {"milestone_id": "M0"},
        "patches": [
            {
                "op": "replace_milestone_steps",
                "milestone_id": "M0",
                "steps": "invalid",
            }
        ],
    }
    try:
        apply_change_to_roadmap_obj(roadmap_obj=roadmap_obj, change_obj=bad_change)
    except ValueError:
        pass
    else:
        raise SystemExit("change_proposals_replace_steps_contract_test failed: expected ValueError for invalid steps")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
