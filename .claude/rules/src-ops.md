---
globs: src/ops/**
---
# Ops Module Rules

- Register new commands in `src/ops/manage.py` dispatch table
- Command naming: kebab-case (e.g., `system-status`, `work-intake-check`)
- All commands accept `--workspace-root` parameter
- Output: structured JSON to stdout or write to `.cache/reports/`
- Evidence: every side-effect writes trace to evidence path
- Contract test: create in `tests/contract/` matching command name
- Use `src.shared.utils` for JSON I/O (load_json, write_json_atomic)
- core_lock applies: CORE_UNLOCK=1 required for src/ writes
