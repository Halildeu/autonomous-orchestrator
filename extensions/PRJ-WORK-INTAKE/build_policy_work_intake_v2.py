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
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def _build_policy(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = repo_root / "policies/work_intake_fragments/manifest.v1.json"
    manifest = _load_json(manifest_path)
    shared = _load_json(repo_root / str(manifest["shared_fragment_path"]))
    rules_dir = repo_root / str(manifest["rules_dir"])
    rule_map: dict[str, dict[str, Any]] = {}
    loaded_fragments: list[str] = []
    for fragment_id in manifest["rule_order"]:
        fragment_path = rules_dir / f"{fragment_id}.v1.json"
        fragment = _load_json(fragment_path)
        loaded_fragments.append(fragment_path.as_posix())
        rules = fragment.get("rules") if isinstance(fragment.get("rules"), list) else []
        for rule in rules:
            rule_id = str(rule.get("id") or "").strip()
            if not rule_id:
                continue
            rule_map[rule_id] = rule
    bucket_rule_order = manifest.get("bucket_rule_order") if isinstance(manifest.get("bucket_rule_order"), list) else []
    bucket_rules = [rule_map[rule_id] for rule_id in bucket_rule_order if rule_id in rule_map]
    policy = dict(shared)
    policy["bucket_rules"] = bucket_rules
    return policy, {"manifest_path": manifest_path.as_posix(), "fragment_paths": loaded_fragments}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    policy, details = _build_policy(repo_root)
    output_path = repo_root / "policies/policy_work_intake.v2.json"
    generated = json.dumps(policy, ensure_ascii=False, indent=2) + "\n"
    current = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    if args.write:
        output_path.write_text(generated, encoding="utf-8")
    if args.check and current != generated:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": "WORK_INTAKE_POLICY_OUT_OF_SYNC",
                    "output_path": output_path.as_posix(),
                    **details,
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
                "output_path": output_path.as_posix(),
                **details,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
