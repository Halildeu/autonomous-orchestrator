# State Machine Rules

- State definitions: `orchestrator/state_machine.v1.json` (schema: `schemas/state-machine.schema.v1.json`)
- Transition guard: call `src.shared.status.validate_transition(from_state, to_state)` BEFORE every state write
- `validate_transition` raises `ValueError` on invalid transition — never suppress this error
- Allowed work_item transitions: OPEN→PLANNED→IN_PROGRESS→APPLIED→CLOSED (forward-only except PLANNED→OPEN, IN_PROGRESS→OPEN)
- Initial writes (no prior state): any valid state is allowed as initial (`"" → *`)
- NOOP is a terminal state for work_items that are skipped
- State changes must be written atomically via `write_json_atomic` — no partial state
- Evidence: every state transition recorded with `from_state`, `to_state`, `timestamp`, `reason`
- Do NOT add new states without updating `orchestrator/state_machine.v1.json` and `src/shared/status.py`
- run_execution and node_execution state guards follow the same pattern — see `src/ops/work_item_state.py` as reference
