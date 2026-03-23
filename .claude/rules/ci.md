---
globs: ci/**
---
# CI Script Rules

- Exit code 0 = pass, non-zero = fail (gate semantics)
- Output: JSON report to stdout or `.cache/reports/`
- Scripts must be idempotent (safe to re-run)
- Use `--dry-run` flag for simulation mode
- File budget: < 800 lines per script
- Import shared utilities from `src.shared.utils`
- Gate scripts: validate_schemas.py, check_standards_lock.py, policy_dry_run.py
