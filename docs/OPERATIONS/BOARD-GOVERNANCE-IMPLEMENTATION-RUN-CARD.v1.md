# Board Governance Implementation Run Card (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: controlled implementation boundary for BOG-3B, BOG-3C, BOG-4B, and BOG-5B  
Current mode: approval/run-card only; no `src`, `.github`, schema, GitHub
Project, issue, PR, label, workflow, or live runtime mutation is authorized by
this document alone

## 1. Purpose

This run card defines how Board Governance implementation may move from
docs-only contracts to source/workflow code without fake completion claims.

It exists because BOG-3B requires source and test files, but current
`write-authorize` evidence blocks `src/**` writes unless a controlled
source-write boundary is active.

Current evidence:

```text
python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path src/ops/commands/board_cmds.py
```

Observed result:

```text
status=BLOCKED
deny_reasons=["CORE_UNLOCK=1 required for src/ writes"]
required_validations=["python3 ci/core_ops_contract_test.py"]
```

Therefore, implementation must remain blocked until the boundary below is
explicitly opened and verified.

## 2. Non-Negotiable Boundary

Allowed before implementation:

- docs-only contracts under `docs/OPERATIONS/`;
- workspace-only manual request / decision / intake records;
- report-only validation commands;
- no live GitHub mutation.

Not allowed before implementation:

- adding `src/ops/board/**`;
- adding `src/ops/commands/board_cmds.py`;
- editing `src/ops/manage.py`;
- adding board tests or fixtures if the active boundary does not authorize them;
- adding `.github/workflows/board-pr-merge-evidence.yml`;
- creating or mutating GitHub Project fields;
- creating or mutating GitHub issues, PRs, labels, or comments;
- claiming BOG-3B, BOG-4B, or BOG-5B implementation as `DONE`.

## 3. Required Approval Class

Implementation requires a narrow operator-approved source-write boundary.

Minimum evidence:

```text
CORE_UNLOCK=1
CORE_UNLOCK_REASON=BOG-3B board governance dry-run implementation
ONE_SHOT_SRC_WINDOW.enabled=true
ONE_SHOT_SRC_WINDOW.ttl_seconds<=3600
ONE_SHOT_SRC_WINDOW.allow_paths=[...]
```

The implementation run must record:

- who/what opened the boundary;
- reason;
- start time;
- expiration time;
- exact allow_paths;
- commands run;
- files changed;
- restore/close evidence after the window.

If any of these are missing, the run must stay report-only.

## 4. BOG-3B Allow Paths

BOG-3B may be implemented only inside this path set:

```text
src/ops/board/__init__.py
src/ops/board/models.py
src/ops/board/rules.py
src/ops/board/reports.py
src/ops/board/fixtures.py
src/ops/commands/board_cmds.py
src/ops/manage.py
tests/contract/test_board_commands.py
fixtures/board/board_list_happy.v1.json
fixtures/board/board_claim_conflict.v1.json
fixtures/board/board_needs_verify_drift.v1.json
fixtures/board/board_malformed_gh_json.v1.json
```

Forbidden in BOG-3B:

- live GitHub writes;
- `apply` mode mutation;
- issue closure;
- `Done` transition automation;
- broad GitHub Project sync;
- network-required tests.

BOG-3B must implement only report/dry-run command behavior with fixture-backed
tests.

## 4.1 BOG-3C Allow Paths

BOG-3C may be implemented only inside this path set:

```text
src/ops/board/apply.py
src/ops/board/rules.py
src/ops/commands/board_cmds.py
tests/contract/test_board_apply.py
fixtures/board/board_apply_happy.v1.json
fixtures/board/board_apply_missing_token.v1.json
fixtures/board/board_apply_project_status.v1.json
```

BOG-3C apply must remain gated:

- `--mode apply` alone is not enough;
- explicit confirmation string is required;
- token env presence is required and token value must not be logged;
- `gh` binary availability is required;
- unsupported actions block before any `gh` call;
- issue close remains unsupported;
- `Done` automation remains forbidden;
- tests must use fake `gh` and must prove no call happens on blocked paths.

## 5. BOG-4B Boundary

BOG-4B is not part of the BOG-3B or BOG-3C source window.

Reason:

- BOG-4B adds a new GitHub workflow surface.
- The current AGENTS allowlist names specific `.github` workflow files and does
  not automatically authorize a new board workflow file.

BOG-4B requires a separate approval boundary for:

```text
.github/workflows/board-pr-merge-evidence.yml
tests/contract/test_board_pr_merge_evidence*.py
fixtures/board/pr_merge_*.v1.json
```

Acceptance remains:

- merged PR with `Tracked by #N` plans/moves eligible issue to `Needs Verify`;
- no automatic `Done`;
- no issue close;
- missing token falls back to report-only;
- idempotent evidence marker prevents duplicate comments.

## 6. BOG-5B Boundary

BOG-5B may follow BOG-3B only after the report/dry-run command structure exists.

Likely allowed path set:

```text
schemas/board-projection.schema.v1.json
src/ops/board/projection.py
src/ops/board/drift.py
tests/contract/test_board_projection*.py
fixtures/board/projection_*.v1.json
```

BOG-5B must remain report/dry-run:

- generate `board_projection.v1.json` under workspace reports;
- report drift categories;
- report digest;
- do not sync or mutate live GitHub Project state.

BOG-5C remains deferred until a dry-run digest is accepted.

## 7. Implementation Sequence

Required sequence:

1. Re-run bootstrap gates:
   - `python3 -m src.ops.manage system-status --workspace-root .cache/ws_customer_default`
   - `python3 -m src.ops.manage portfolio-status --workspace-root .cache/ws_customer_default`
2. Confirm write boundary:
   - `python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path src/ops/commands/board_cmds.py`
3. Implement BOG-3B source and fixture tests only when write-authorize passes.
4. Run required validations:
   - `python3 ci/core_ops_contract_test.py`
   - `python3 ci/validate_schemas.py`
   - `python3 -m src.ops.manage policy-check --source both`
   - `python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default`
5. Run board command tests.
6. Close/restore the one-shot source window.
7. Update adoption plan statuses with evidence.

If any validation fails, keep BOG-3B below `DONE` and record the failure.

## 8. Validation Contract

Minimum BOG-3B test coverage:

| Scenario | Required result |
|---|---|
| no GitHub token | `BLOCKED` or report-only; no mutation |
| malformed GitHub JSON | `ERROR`; no mutation |
| issue missing `project-roadmap` | not claimable |
| issue missing `agent-state:v1` | drift finding |
| active competing claim | current session loses |
| expired claim | reclaim candidate |
| `Kind=umbrella` claim attempt | `BLOCKED` |
| `Needs Verify` without label | drift finding |
| forbidden close keyword | drift finding |
| `--mode apply` | blocked until BOG-3C |

Every command output must include:

- command name;
- mode;
- status;
- findings;
- planned_actions;
- applied_actions;
- blocked_reasons;
- evidence;
- non-empty `does_not_prove`.

## 9. Stop Conditions

Stop immediately if:

- write-authorize remains `BLOCKED`;
- allow_paths widen beyond this run card without a new decision;
- `src/**` edits occur outside the active window;
- workflow files are edited during BOG-3B;
- tests require live GitHub credentials;
- any command plans `Done` or issue close for runtime/governance work;
- a secret or token appears in logs, reports, or fixtures;
- validation reports schema/policy/doc-nav failure.

## 10. Evidence To Record

Implementation evidence must include:

- `git status --short --branch` before and after;
- write-authorize output before source edits;
- changed file list;
- contract test output;
- schema validation output;
- policy-check output;
- doc-nav-check output;
- board command test output;
- one-shot window restore/close evidence;
- adoption plan status update.

Evidence must state what it does not prove. Passing dry-run tests does not prove
live GitHub Project mutation safety.

## 11. Current Decision

Current decision:

```text
Do not implement BOG-3B/3C/4B/5B source or workflow code until the required
source/workflow write boundary is explicitly opened and evidenced.
```

This keeps the Board Governance line honest: docs may advance, but
implementation status remains blocked or TODO until code, tests, and gates
actually exist.

## 12. Acceptance

This run card is `REVIEW_READY` when:

- it names the current blocker;
- it defines the required approval class;
- it defines BOG-3B allow_paths;
- it separates BOG-4B workflow authorization from BOG-3B source authorization;
- it defines BOG-5B dry-run boundary;
- it defines required validation commands;
- it defines stop conditions;
- it defines implementation evidence;
- the adoption plan and SSOT map link this run card;
- docs write authorization passes;
- no source, workflow, GitHub Project, issue, PR, label, or live runtime
  mutation was made.
