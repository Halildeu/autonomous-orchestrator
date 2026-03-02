# Criteria v1

- tenant_id: TENANT-DEFAULT
- version: v1
- success_criteria:
  - Phase execution must complete with reproducible evidence.
  - Critical extension warnings and failures should be zero.
  - System status and risk outputs must be visible in a single report.
- quality_criteria:
  - JSON-first artifacts stay schema-compatible.
  - Required tenant documents are present and versioned.
  - Operations remain fail-closed on uncertain state.

