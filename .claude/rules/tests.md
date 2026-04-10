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
