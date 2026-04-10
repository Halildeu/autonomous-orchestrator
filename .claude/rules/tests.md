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

## Design System Test Rules (dev repo: @mfe/design-system)

- Depth tests (.depth.test.tsx) MUST import the real component from parent directory
- NEVER render `<div>` or raw HTML as substitute for actual component
- NEVER add `quality-depth-boost` or `quality-edge-boost` markers
- `// depth-keep` directive exempts files from fake-test detection
- CI gate: `design-system-doctor --gate=fake-test-detection` blocks merge
- Generate baselines: `npm run test:generate-depth` (props-aware, ts-morph)
- Scan for fakes: `npm run test:cleanup-fakes`
