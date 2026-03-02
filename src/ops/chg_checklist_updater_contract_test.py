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


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"chg_checklist_updater_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.ops.chg_checklist_updater import update_checklist_step

    ws = repo_root / ".cache" / "ws_chg_checklist_updater_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    plan_path = ws / "CHG-TEST.plan.json"
    seed = {
        "chg_id": "CHG-TEST",
        "extension_id": "EXT-X",
        "gate": "test-gate",
        "owner": "CORE",
        "eta": "2026-02-09",
        "priority": "P1",
        "objective": "contract",
        "execution_checklist": [
            {
                "id": "P1-02",
                "title": "Test step",
                "status": "TODO",
                "owner": "CORE",
                "eta": "2026-02-09",
                "evidence_paths": [],
            }
        ],
    }
    plan_path.write_text(json.dumps(seed, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    doing = update_checklist_step(
        plan_path=plan_path,
        step_id="P1-02",
        status="DOING",
        note="başladı",
        evidence_paths=[".cache/reports/a.json"],
        owner="CORE",
        eta="2026-02-09",
    )
    _must(doing.get("status") == "OK", "doing update failed")

    done = update_checklist_step(
        plan_path=plan_path,
        step_id="P1-02",
        status="DONE",
        note="bitti",
        evidence_paths=[".cache/reports/b.json"],
        owner="CORE",
        eta="2026-02-09",
    )
    _must(done.get("status") == "OK", "done update failed")

    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    step = saved.get("execution_checklist", [])[0]
    _must(step.get("status") == "DONE", "status should be DONE")
    _must(bool(step.get("started_at")), "started_at missing")
    _must(bool(step.get("finished_at")), "finished_at missing")
    evid = step.get("evidence_paths") if isinstance(step.get("evidence_paths"), list) else []
    _must(".cache/reports/a.json" in evid and ".cache/reports/b.json" in evid, "evidence merge failed")
    hist = step.get("status_history") if isinstance(step.get("status_history"), list) else []
    _must(len(hist) >= 2, "status history should have at least 2 entries")

    md_path = plan_path.with_suffix(".md")
    _must(md_path.exists(), "markdown output missing")
    md_text = md_path.read_text(encoding="utf-8")
    _must("[x] P1-02 Test step" in md_text, "md checklist not rendered as done")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
