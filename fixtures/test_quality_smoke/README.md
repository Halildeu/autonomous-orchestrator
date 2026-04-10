# Test Quality Smoke Fixtures

Positive and negative match examples for the test quality gate (PRJ-TEST-QUALITY-GATE).

## Files

| File | Expected Result | Rules |
|------|----------------|-------|
| bad_shallow_test.tsx | MATCH | TQ-001, EP-006 |
| bad_tautological_test.tsx | MATCH | TQ-002, EP-007 |
| bad_no_import_test.tsx | MATCH | TQ-004 |
| bad_mock_heavy_test.tsx | MATCH | TQ-005 |
| good_real_test.tsx | NO MATCH | None |

## Usage

```bash
python3 ci/check_test_quality.py --repo-root . --scan-path fixtures/test_quality_smoke --dry-run
```
