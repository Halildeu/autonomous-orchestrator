from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"contract_hardening_test failed: not object: {path}")
    return obj


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"contract_hardening_test failed: {message}")


def _rule_ids_from_matrix(matrix: dict) -> set[str]:
    profiles = matrix.get("profiles")
    _must(isinstance(profiles, dict), "severity matrix profiles missing")
    default_profile = profiles.get("default_profile")
    _must(isinstance(default_profile, dict), "default_profile missing")
    return {k for k in default_profile if isinstance(k, str) and k.startswith("EP-")}


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ext_root = Path(__file__).resolve().parents[1]

    manifest = _load_json(ext_root / "extension.manifest.v1.json")
    manifest_schema = _load_json(repo_root / "schemas" / "extension-manifest.schema.v1.json")
    Draft202012Validator(manifest_schema).validate(manifest)

    contract_schema = _load_json(ext_root / "contract" / "enforcement-check.schema.v1.json")
    contract_example = _load_json(ext_root / "contract" / "enforcement-check.example.v1.json")
    Draft202012Validator(contract_schema).validate(contract_example)

    stats = contract_example.get("stats")
    _must(isinstance(stats, dict), "example stats missing")
    _must(stats.get("totals", {}).get("violations_count") == len(contract_example.get("violations", [])), "example totals.violations_count mismatch")

    self_hit = stats.get("self_hit")
    _must(isinstance(self_hit, dict), "self_hit block missing")
    exclude_globs = self_hit.get("exclude_globs")
    _must(isinstance(exclude_globs, list) and bool(exclude_globs), "self_hit exclude_globs missing")
    _must(
        "extensions/PRJ-ENFORCEMENT-PACK/semgrep/rules/**" in exclude_globs,
        "self_hit exclude_globs must include rule self-path",
    )

    baseline = stats.get("false_positive_baseline")
    _must(isinstance(baseline, dict), "false_positive_baseline missing")
    baseline_file = _load_json(ext_root / "contract" / "false_positive_baseline.v1.json")

    _must(isinstance(baseline_file.get("totals"), dict), "baseline file totals missing")
    _must(baseline_file.get("totals") == baseline.get("totals"), "baseline totals drift between example and baseline file")

    matrix = _load_json(ext_root / "contract" / "severity_matrix.v1.json")
    expected_rules = _rule_ids_from_matrix(matrix)
    baseline_rules = {x.get("rule_id") for x in baseline.get("by_rule", []) if isinstance(x, dict)}
    baseline_file_rules = {x.get("rule_id") for x in baseline_file.get("by_rule", []) if isinstance(x, dict)}

    _must(expected_rules == baseline_rules, "severity matrix vs example baseline rule_id drift")
    _must(expected_rules == baseline_file_rules, "severity matrix vs baseline file rule_id drift")

    for entry in baseline.get("by_rule", []):
        _must(isinstance(entry, dict), "baseline by_rule entry invalid")
        findings = int(entry.get("findings_count", 0))
        sampled = int(entry.get("sampled_count", 0))
        false_positives = int(entry.get("false_positive_count", 0))
        _must(sampled <= findings, f"sampled_count exceeds findings_count for {entry.get('rule_id')}")
        _must(false_positives <= sampled, f"false_positive_count exceeds sampled_count for {entry.get('rule_id')}")

    expected_exclude = "extensions/PRJ-ENFORCEMENT-PACK/semgrep/rules/**"
    rules_dir = ext_root / "semgrep" / "rules"
    for rule_file in sorted(rules_dir.glob("ep*.yaml")):
        text = rule_file.read_text(encoding="utf-8")
        _must(expected_exclude in text, f"self-hit exclude missing in {rule_file.name}")
        _must("ep_id:" in text, f"ep_id metadata missing in {rule_file.name}")

    print(json.dumps({"status": "OK", "extension_id": "PRJ-ENFORCEMENT-PACK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
