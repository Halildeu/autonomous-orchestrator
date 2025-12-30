import json
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_sorted(paths):
    return sorted(paths, key=lambda p: str(p))


def validate_schema_files(repo_root: Path) -> list[Path]:
    schema_paths = iter_sorted((repo_root / "schemas").glob("*.schema.json"))
    if not schema_paths:
        raise SystemExit("No schemas found in schemas/*.schema.json")

    for schema_path in schema_paths:
        Draft202012Validator.check_schema(load_json(schema_path))

    return schema_paths


def validate_request_envelope_fixtures(repo_root: Path) -> tuple[int, int]:
    schema_path = repo_root / "schemas" / "request-envelope.schema.json"
    if not schema_path.exists():
        print("WARN: schemas/request-envelope.schema.json not found; skipping fixture validation.")
        return (0, 0)

    validator = Draft202012Validator(load_json(schema_path))
    fixture_paths = iter_sorted((repo_root / "fixtures" / "envelopes").glob("*.json"))
    if not fixture_paths:
        print("WARN: No fixtures found in fixtures/envelopes/*.json; skipping.")
        return (0, 0)

    negative_fixture_paths = [p for p in fixture_paths if p.name.endswith("_invalid.json")]
    positive_fixture_paths = [p for p in fixture_paths if not p.name.endswith("_invalid.json")]

    invalid = 0
    for fixture_path in positive_fixture_paths:
        instance = load_json(fixture_path)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
        if errors:
            invalid += 1
            print(f"INVALID: {fixture_path}")
            for err in errors[:10]:
                where = err.json_path or "$"
                print(f"  - {where}: {err.message}")

    unexpected_valid_negatives = 0
    for fixture_path in negative_fixture_paths:
        instance = load_json(fixture_path)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
        if not errors:
            unexpected_valid_negatives += 1
            print(f"UNEXPECTED_VALID_NEGATIVE: {fixture_path}")

    total_checked = len(positive_fixture_paths) + len(negative_fixture_paths)
    if total_checked != len(fixture_paths):
        raise SystemExit("Internal error: fixture classification mismatch.")

    if unexpected_valid_negatives:
        invalid += unexpected_valid_negatives

    return (len(positive_fixture_paths), invalid)


def main():
    repo_root = Path(__file__).resolve().parents[1]

    schema_paths = validate_schema_files(repo_root)
    total_fixtures, invalid_fixtures = validate_request_envelope_fixtures(repo_root)

    if invalid_fixtures:
        raise SystemExit(f"Schema validation failed: {invalid_fixtures}/{total_fixtures} invalid fixtures.")

    print(f"OK: {len(schema_paths)} schema files validated.")
    if total_fixtures:
        print(f"OK: {total_fixtures} fixtures validated against request-envelope schema.")


if __name__ == "__main__":
    main()
