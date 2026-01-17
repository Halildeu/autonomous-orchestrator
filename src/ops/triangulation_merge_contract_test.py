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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.ops.context_pack_triangulate import run_context_pack_triangulate

    ws = repo_root / ".cache" / "ws_triangulation_test"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    responses_dir = ws / ".cache" / "inputs"
    resp1 = responses_dir / "resp1.json"
    resp2 = responses_dir / "resp2.json"
    resp3 = responses_dir / "resp3.json"

    _write_json(resp1, {"provider_id": "p1", "model_id": "m1", "field_a": "X", "field_b": 1, "field_c": "A"})
    _write_json(resp2, {"provider_id": "p2", "model_id": "m2", "field_a": "X", "field_b": 2, "field_c": "B"})
    _write_json(resp3, {"provider_id": "p3", "model_id": "m3", "field_a": "Y", "field_b": 2, "field_c": "C"})

    res = run_context_pack_triangulate(
        workspace_root=ws,
        responses=[str(resp1), str(resp2), str(resp3)],
        out=None,
    )
    if res.get("status") != "OK":
        raise SystemExit("triangulation_merge_contract_test failed: status not OK")

    merge_path = ws / ".cache" / "index" / "context_pack_merge.v1.json"
    if not merge_path.exists():
        raise SystemExit("triangulation_merge_contract_test failed: merge output missing")

    merge_obj = json.loads(merge_path.read_text(encoding="utf-8"))
    merged = merge_obj.get("merged") if isinstance(merge_obj, dict) else {}
    if merged.get("field_a") != "X":
        raise SystemExit("triangulation_merge_contract_test failed: field_a majority")
    if merged.get("field_b") != 2:
        raise SystemExit("triangulation_merge_contract_test failed: field_b majority")
    disagreements = merge_obj.get("disagreements") if isinstance(merge_obj, dict) else []
    if not any(d.get("field") == "field_c" for d in disagreements if isinstance(d, dict)):
        raise SystemExit("triangulation_merge_contract_test failed: field_c disagreement missing")

    merge_again = run_context_pack_triangulate(
        workspace_root=ws,
        responses=[str(resp1), str(resp2), str(resp3)],
        out=None,
    )
    if merge_again.get("merge_path") != res.get("merge_path"):
        raise SystemExit("triangulation_merge_contract_test failed: merge path not stable")

    merge_obj_again = json.loads(merge_path.read_text(encoding="utf-8"))
    merge_obj.pop("generated_at", None)
    merge_obj_again.pop("generated_at", None)
    if json.dumps(merge_obj, sort_keys=True) != json.dumps(merge_obj_again, sort_keys=True):
        raise SystemExit("triangulation_merge_contract_test failed: merge output not deterministic")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
