from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    manifest = _load_json(repo_root / "policies/work_intake_fragments/manifest.v1.json")
    shared = _load_json(repo_root / str(manifest["shared_fragment_path"]))
    rules_dir = repo_root / str(manifest["rules_dir"])
    rule_map: dict[str, dict[str, Any]] = {}
    fragment_paths: list[str] = []
    for fragment_id in manifest["rule_order"]:
        fragment_path = rules_dir / f"{fragment_id}.v1.json"
        fragment = _load_json(fragment_path)
        fragment_paths.append(fragment_path.as_posix())
        rules = fragment.get("rules") if isinstance(fragment.get("rules"), list) else []
        for rule in rules:
            rule_id = str(rule.get("id") or "").strip()
            if not rule_id:
                continue
            rule_map[rule_id] = rule

    bucket_rule_order = manifest.get("bucket_rule_order") if isinstance(manifest.get("bucket_rule_order"), list) else []
    bucket_rules = [rule_map[rule_id] for rule_id in bucket_rule_order if rule_id in rule_map]

    generated = dict(shared)
    generated["bucket_rules"] = bucket_rules
    current_path = repo_root / str(manifest["output_path"])
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if current != generated:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "WORK_INTAKE_POLICY_OUT_OF_SYNC",
                    "output_path": current_path.as_posix(),
                    "manifest_path": (repo_root / "policies/work_intake_fragments/manifest.v1.json").as_posix(),
                    "fragment_paths": fragment_paths,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "OK",
                "output_path": current_path.as_posix(),
                "manifest_path": (repo_root / "policies/work_intake_fragments/manifest.v1.json").as_posix(),
                "fragment_paths": fragment_paths,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
