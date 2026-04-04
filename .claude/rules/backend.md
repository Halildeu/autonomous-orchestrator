# Backend Domain Rules

- Python type hints required for all public functions
- Import shared utilities from src.shared.utils (load_json, write_json_atomic, now_iso8601, sha256_text)
- Logging: use src.shared.logger.get_logger(__name__) — never print() for structured output
- Script budget: soft limit 1200 lines, hard limit 2000 lines per file
- Atomic writes: use write_json_atomic() for all JSON file writes — never raw open()
- Status transitions: call validate_transition() before every state write
- Auth architecture: Keycloak = login only, ALL authorization via permission-service/OpenFGA
- No auth logic in application code — delegate to permission-service middleware
- Error handling: fail-closed, always produce structured error output
- Self-hosted deployment — no cloud-specific service dependencies
- Evidence: every side-effect must produce an evidence trace
- Secrets: NEVER log/evidence tokens, keys, or passwords
- Register new ops commands in src/ops/manage.py dispatch table
- Command naming: kebab-case (e.g., system-status, work-intake-check)
- All commands accept --workspace-root parameter
