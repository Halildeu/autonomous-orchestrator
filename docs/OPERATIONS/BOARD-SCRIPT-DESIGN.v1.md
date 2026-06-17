# Board Script Design (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-3A minimal board tooling design  
Current mode: design-only; no script, ops command, GitHub Project, issue, PR, workflow, label, or source/runtime mutation is authorized by this document alone

## 1. Purpose

This document defines the minimal board tooling design before implementation.
The goal is deterministic, auditable, fail-closed tooling for the governance
board without creating hidden live GitHub side effects.

The first implementation must be dry-run/report-only by default and must work
against fake `gh` fixtures before any live GitHub write mode exists.

## 2. Non-Negotiable Invariants

All future board tooling must obey these invariants:

- Repo SSOT remains authority.
- Board is not an intake firehose.
- Only `project-roadmap` may act as board ingestion signal.
- `Backlog` is not claimable.
- `Kind=umbrella` is not claimable.
- Claim identity is session/worktree/branch, not only GitHub assignee.
- `Tracked by` is the default PR relation for board-visible work.
- PR merge must not auto-mark runtime/governance work `Done`.
- No script may mark runtime/governance work `Done`.
- No script may close issues in the initial implementation.
- Missing token, ambiguous target, malformed issue body, or conflicting claim
  must fail closed.
- First enforcement mode is report-only.

## 3. Proposed Command Surface

The future command group should be exposed through the existing ops entrypoint:

```text
python3 -m src.ops.manage board-list
python3 -m src.ops.manage board-claim
python3 -m src.ops.manage board-heartbeat
python3 -m src.ops.manage board-release
python3 -m src.ops.manage board-verify
python3 -m src.ops.manage board-backlog-add
```

These command names match the adoption plan. Implementation may internally live
under `src/ops/commands/` and helper modules, but user-facing execution should
stay program-led through `src.ops.manage`.

## 4. Global Flags

Every command must support:

```text
--workspace-root <path>
--repo <owner/name>
--board-title <title>
--mode report|dry-run|apply
--out <path>
--gh-bin <path>
```

Defaults:

| Flag | Default |
|---|---|
| `--workspace-root` | `.cache/ws_customer_default` |
| `--repo` | inferred only when unambiguous, otherwise fail closed |
| `--board-title` | `autonomous-orchestrator Governance Board` |
| `--mode` | `report` |
| `--out` | workspace report path |
| `--gh-bin` | `gh` |

Mode semantics:

| Mode | Network | GitHub writes | Repo writes | Use |
|---|---|---|---|---|
| `report` | no required network | no | report only | local validation and fixture tests |
| `dry-run` | read-only allowed if explicitly configured | no | workspace report only | live inventory without mutation |
| `apply` | allowed only with explicit operator approval | limited | workspace report + live mutation ledger | later BOG step only |

BOG-3B may implement `report` and fixture-backed `dry-run`. It must not
implement live `apply` unless BOG-3C acceptance criteria and operator boundary
exist.

## 5. Output Contract

Every command must emit JSON to stdout and optionally write the same payload to
`--out`.

Minimum shape:

```json
{
  "version": "v1",
  "command": "board-list",
  "mode": "report",
  "status": "OK",
  "repo": "owner/name",
  "board_title": "autonomous-orchestrator Governance Board",
  "started_at": "2026-06-17T00:00:00Z",
  "completed_at": "2026-06-17T00:00:00Z",
  "inputs": {},
  "findings": [],
  "planned_actions": [],
  "applied_actions": [],
  "blocked_reasons": [],
  "evidence": {
    "source": [],
    "desired_state": [],
    "runtime_live": [],
    "browser_user_path": [],
    "does_not_prove": []
  }
}
```

Rules:

- `applied_actions` must be empty outside `apply`.
- `does_not_prove` must never be empty.
- `status` must be one of `OK`, `WARN`, `BLOCKED`, `ERROR`.
- `BLOCKED` means no mutation was attempted.
- Any live mutation in future `apply` mode must record before/after evidence.

## 6. Command Contracts

### board-list

Purpose: report board-eligible issues and board/body drift.

Inputs:

- repository issues with `project-roadmap`,
- board items for the target Project,
- field/label contract,
- issue body contract.

Reports:

- open `project-roadmap` issues missing from board,
- board items without `project-roadmap`,
- missing board fields,
- invalid `Kind=umbrella` with `In Progress`,
- `Needs Verify` without `needs-verification`,
- `Done` with `needs-verification` or `blocked`,
- malformed or missing `agent-state:v1`.

Allowed mutation: none.

### board-claim

Purpose: claim one eligible issue for an agent session.

Required inputs:

- `--issue <number>`
- `--session <id>`
- `--agent <codex|claude|human|...>`
- `--worktree <path>`
- `--branch <branch>`
- `--ttl-seconds <seconds>`

Eligibility:

- issue has `project-roadmap`,
- `Status=Todo`,
- `Kind` is not `umbrella`,
- no active non-expired claim wins before this session,
- issue body has parseable `agent-state:v1`.

Planned mutation in future apply mode:

- append `CLAIM` comment,
- update `agent-state:v1`,
- set board `Status=In Progress`.

Initial implementation: report planned mutation only.

### board-heartbeat

Purpose: extend an active claim.

Required inputs:

- `--issue <number>`
- `--session <id>`
- `--ttl-seconds <seconds>`

Eligibility:

- current claim session matches,
- claim is not expired,
- issue is still `In Progress`.

Planned mutation in future apply mode:

- append `HEARTBEAT` comment,
- update `claim_updated_at`,
- update `expires_at`.

Initial implementation: report planned mutation only.

### board-release

Purpose: release a claim or hand off work.

Required inputs:

- `--issue <number>`
- `--session <id>`
- `--reason <completed|blocked|lost-race|manual-handoff|stale-cleanup>`

Planned mutation in future apply mode:

- append `HANDOFF` or `BLOCKED` comment,
- clear claim fields,
- set `Status=Todo`, `Blocked`, or `Needs Verify` according to evidence.

Forbidden:

- marking `Done`,
- closing issue,
- removing evidence.

Initial implementation: report planned mutation only.

### board-verify

Purpose: move source-ready items toward verified state without premature close.

Required inputs:

- `--issue <number>`
- `--evidence <path-or-url-or-run-id>`
- `--evidence-type source|desired-state|runtime-live|browser-user-path`

Planned mutation in future apply mode:

- append `EVIDENCE` or `READY-FOR-VERIFY` comment,
- update issue body evidence section,
- move to `Needs Verify` when source evidence exists and acceptance remains.

Forbidden:

- marking runtime/governance work `Done`,
- closing issue,
- claiming evidence that is not inspectable.

Initial implementation: report planned mutation only.

### board-backlog-add

Purpose: capture a curated board candidate without broad auto-ingestion.

Required inputs:

- `--title <title>`
- `--kind <milestone|gate|risk|issue|umbrella>`
- `--faz <value>`
- `--track <value>`
- `--priority <P0|P1|P2|P3>`
- `--ssot-ref <path-or-id>`
- `--next-action <text>`

Planned mutation in future apply mode:

- create issue using the issue template contract,
- add `project-roadmap`,
- populate board fields,
- set `Status=Backlog` or `Todo` based on triage completeness.

Forbidden:

- creating issues without `project-roadmap`,
- creating broad untriaged intake,
- creating secret-bearing issues.

Initial implementation: report planned mutation only.

## 7. GitHub Adapter Boundary

All GitHub interaction must go through a narrow adapter layer.

Adapter responsibilities:

- execute `gh` commands or fake fixture commands,
- collect stdout/stderr/exit code,
- parse JSON with structured parsers,
- redact tokens and secrets,
- return typed results to command logic.

Command logic must not shell out directly in scattered places.

The adapter must support:

```text
real gh binary
fake gh binary
fixture JSON files
forced failure exits
malformed JSON responses
missing token responses
rate-limit-like responses
```

## 8. Fake-gh Test Strategy

BOG-3B must include tests that do not need network or a real GitHub token.

Required fixture scenarios:

| Scenario | Expected result |
|---|---|
| no token / auth failure | `BLOCKED`, no planned live mutation |
| project not found | `BLOCKED` with target ambiguity reason |
| issue missing `project-roadmap` | not claimable, reported |
| issue missing `agent-state:v1` | drift finding |
| expired claim | reclaim candidate |
| active competing claim | current session loses, no mutation |
| `Kind=umbrella` claim attempt | `BLOCKED` |
| `Needs Verify` without label | drift finding |
| forbidden close keyword in PR | drift finding |
| malformed gh JSON | `ERROR`, no mutation |

Tests must verify that:

- `apply` is unavailable or blocked until BOG-3C,
- no command returns an applied action in `report` or `dry-run`,
- no command plans a `Done` transition for runtime/governance work,
- output JSON always includes `does_not_prove`.

## 9. Implementation Placement

Preferred future implementation:

```text
src/ops/board/
  __init__.py
  commands.py
  gh_adapter.py
  models.py
  parser.py
  rules.py
  reports.py
src/ops/commands/board_cmds.py
tests/contract/test_board_*.py
fixtures/board/
```

Rationale:

- board logic is separated from argparse registration,
- parser/rules can be unit tested without network,
- fake fixtures can cover edge cases,
- command registration follows existing `src.ops.manage` style.

## 10. Security and Secrets

Scripts must never print:

- GitHub tokens,
- Authorization headers,
- private email addresses,
- token-bearing URLs,
- raw environment dumps.

Redaction rules must apply to stdout, stderr, report files, and error payloads.

If a response contains a suspected secret, command status must become `BLOCKED`
or `ERROR` and the report must store only a redacted value.

## 11. BOG-3A Acceptance

BOG-3A is `REVIEW_READY` when:

- this file exists,
- it defines every command named in the adoption plan,
- it defines global modes and dry-run/report-only semantics,
- it defines output JSON shape,
- it defines fake-gh fixture strategy,
- it defines fail-closed behavior,
- it forbids initial `Done` and issue close automation,
- `BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md` records this design,
- `SSOT-MAP.md` links this design,
- write authorization for this docs path passes,
- schema/policy/doc-nav checks still pass,
- no script, ops command, GitHub Project, issue, PR, workflow, label, or
  source/runtime mutation was made.

BOG-3A is not implementation. BOG-3B must implement only the dry-run/report
subset with fake-gh tests before any live apply mode is considered.
