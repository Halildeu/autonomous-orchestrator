# Infrastructure Domain Rules

- CI scripts: exit code 0 = pass, non-zero = fail (gate semantics)
- Scripts must be idempotent (safe to re-run)
- Use --dry-run flag for simulation mode
- File budget: < 800 lines per script
- Import shared utilities from src.shared.utils
- Docker: multi-stage builds preferred, minimize image layers
- GitHub Actions: use pinned action versions (not @latest)
- Secrets: never hardcode — use environment variables or secret managers
- YAML: 2-space indent, UTF-8
- Workflow naming: kebab-case (e.g., gate-enforcement-check.yml)
