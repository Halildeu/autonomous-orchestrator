---
globs: tests/**
---
# Test Rules

- Framework: pytest
- Fixtures in `fixtures/` directory (envelopes, schemas, policies)
- Contract tests: `tests/contract/test_<command_name>.py`
- Naming: `test_<description>` (snake_case)
- Run: `pytest tests/ -x` (fail-fast)
- Coverage: focus on ops commands and shared utilities
- No network calls in tests (offline-first)
- Use tmp_path fixture for workspace isolation

## Fake Test Prohibition (MUST)

Policy ref: `policies/policy_test_quality.v1.json` (6 TQ rules, blocking enforcement)

- NEVER generate a test that only renders a component and checks `toBeInTheDocument()` / `toBeTruthy()` / `toMatchSnapshot()` with no interaction (TQ-001)
- NEVER use `expect(true).toBe(true)` or any literal-to-literal tautological assertion (TQ-002)
- NEVER copy-paste the same test body across multiple test files — each test must exercise unique behavior (TQ-003)
- NEVER create a test file that does not import the component it claims to test (TQ-004)
- EVERY `it()` / `test()` block MUST have at least 2 meaningful assertions
- EVERY component test MUST include at least one of: user interaction (fireEvent/userEvent), prop variation, state change verification, callback invocation check
- If test coverage is needed, write FEWER tests with DEEPER assertions rather than many shallow tests
- Zero tolerance for bulk-generation markers: `quality-edge-boost`, `auto-generated-test`, `test-scaffold` (TQ-006)

## Test Quality Metrics

- Minimum assertion density: 2 per test case
- Maximum shallow-render ratio: 10% of test suite
- Maximum duplication ratio: 5%
- CI gate: `python3 ci/check_test_quality.py --repo-root . --dry-run`
