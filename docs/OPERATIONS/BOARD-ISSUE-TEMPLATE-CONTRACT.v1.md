# Board Issue Template Contract (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-2A issue body and future GitHub Issue Form contract  
Current mode: docs-only; no `.github/ISSUE_TEMPLATE`, GitHub issue, Project, PR, workflow, label, or source/runtime mutation is authorized by this document alone

## 1. Purpose

This contract defines the issue body shape for board-eligible work so a fresh
agent session can safely understand, claim, execute, verify, and hand off work
without relying on hidden chat context.

The contract is designed for later implementation as a GitHub Issue Form, but
this file does not create or activate that form.

## 2. Applicability

Use this contract for issues that are intended to appear on the governance
board.

Required ingestion signal:

```text
project-roadmap
```

Do not use this contract for:

- routine small code fixes,
- dependency noise,
- exploratory notes,
- PR-only source changes that do not require board tracking,
- broad intake where the item has not been triaged,
- private or secret-bearing content.

An issue created from this contract is not fully tracked until the board fields
from `BOARD-FIELD-LABEL-CONTRACT.v1.md` are populated.

## 3. Required Issue Types

| Template type | Intended `Kind` | Use |
|---|---|---|
| Board work item | `issue` | scoped executable work |
| Board gate | `gate` | readiness/check gate that can pass, fail, or block |
| Board risk | `risk` | risk/RAID item requiring mitigation or decision |
| Board milestone | `milestone` | phase-level outcome that links child work |
| Board umbrella | `umbrella` | non-claimable grouping issue |

The first implementation may ship one issue form with a required `Kind` field.
Separate issue forms are optional and should wait until duplication becomes
useful.

## 4. Required Labels

Every issue using this contract must carry:

```text
project-roadmap
```

Conditional labels:

| Condition | Required label |
|---|---|
| `Kind=risk` | `risk` |
| `Kind=gate` | `gate` |
| `Status=Blocked` | `blocked` |
| `Status=Needs Verify` | `needs-verification` |
| security-sensitive work | `security` |
| quality/test/verification work | `quality` |

Labels refine board meaning. Only `project-roadmap` may act as board ingestion
signal.

## 5. Required Body Sections

Every executable board issue must include these sections in this order:

1. `Agent State`
2. `Board Fields`
3. `Context`
4. `Acceptance Criteria`
5. `Evidence`
6. `Remaining`
7. `Next Action`
8. `Related`
9. `Safety Notes`

The order is intentional. Later scripts should parse the issue body using stable
headings, not loose prose.

## 6. Agent State Block

Every executable board issue must contain exactly one `agent-state:v1` HTML
comment block.

Initial state:

```markdown
## Agent State

<!-- agent-state:v1
status: todo
claim_session: none
claim_agent: none
claim_worktree: none
claim_branch: none
claim_started_at: none
claim_updated_at: none
expires_at: none
last_verified_at: none
-->
```

Allowed `status` values:

| Value | Meaning |
|---|---|
| `backlog` | captured but not triaged |
| `todo` | triaged and claimable |
| `in_progress` | active claim exists |
| `blocked` | waiting on external dependency or decision |
| `needs_verify` | source-ready; acceptance pending |
| `done_candidate` | evidence appears complete; closure not yet final |
| `closed` | issue deliberately closed after evidence |

Rules:

- `claim_session`, `claim_agent`, `claim_worktree`, and `claim_branch` are
  required when `status=in_progress`.
- `expires_at` is required when `status=in_progress`.
- `last_verified_at` is required when moving to `needs_verify` or
  `done_candidate`.
- Do not store secrets, tokens, private URLs, or personal contact details in the
  block.
- The block is current-state metadata; comments remain append-only audit log.

## 7. Board Fields Section

Required section:

```markdown
## Board Fields

**Status:** Todo
**Faz:** F2 Issue PR Contract
**Track:** github-ops
**Priority:** P1
**Kind:** issue
**Owner repo:** <owner/repo>
**Board:** autonomous-orchestrator Governance Board
**SSOT refs:**
- docs/OPERATIONS/BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md
```

Field values must match `BOARD-FIELD-LABEL-CONTRACT.v1.md`.

`SSOT refs` must point to repo files, roadmap items, policies, schemas, or
decision records that define why the issue exists. Chat-only context is not
sufficient.

## 8. Context Section

Required section:

```markdown
## Context

<One paragraph explaining the problem, why it matters, and which SSOT or gate
created the work.>
```

The context must answer:

- What is the problem or gap?
- Why is it board-visible?
- Which SSOT source or gate proves it exists?
- What is out of scope?

## 9. Acceptance Criteria Section

Required section:

```markdown
## Acceptance Criteria

- [ ] <observable outcome>
- [ ] <verification command or evidence path>
- [ ] <explicit non-goal or boundary, where relevant>
```

Acceptance criteria must be observable and testable. Do not use vague criteria
such as "improve", "clean up", "make better", or "finish setup" without a
specific evidence source.

At least one acceptance criterion must state what is not proven by the expected
evidence when runtime or user-path verification is still pending.

## 10. Evidence Section

Required section:

```markdown
## Evidence

### Source
- Pending

### Desired-state
- Pending

### Runtime/live
- Pending

### Browser/user-path
- Pending

### Does not prove
- Pending
```

Rules:

- `Source` proves file, code, schema, policy, or doc changes.
- `Desired-state` proves declared target state.
- `Runtime/live` proves actual external system state.
- `Browser/user-path` proves user-visible behavior where applicable.
- `Does not prove` is mandatory and must not be removed.
- Evidence must reference paths, command outputs, PRs, run IDs, screenshots, or
  other inspectable artifacts.
- Do not paste secrets or token-bearing URLs.

## 11. Remaining Section

Required section:

```markdown
## Remaining

- Blocking:
- Non-blocking:
- Deferred:
```

Rules:

- A blocking item must name the unblock owner or required external state.
- A deferred item must name the future BOG step, roadmap item, or decision that
  will handle it.
- Empty `Remaining` sections are allowed only when the issue is a
  `DONE-CANDIDATE`.

## 12. Next Action Section

Required section:

```markdown
## Next Action

<The first concrete action a fresh session should take.>
```

The next action must be single-step and executable by an agent. It must not ask
the user to run a shell command.

Examples:

- `Run write-authorize for docs/OPERATIONS/<file> and draft the docs-only contract.`
- `Read PR #123 and verify whether it used Tracked by #456.`
- `Run dry-run board preflight and attach the report path.`

## 13. Related Section

Required section:

```markdown
## Related

**Tracked by:** <board issue or "self">
**Related PRs:** none
**Related decisions:** none
**Related roadmap items:** none
```

Rules:

- Runtime, GitOps, governance, and acceptance work must prefer `Tracked by`.
- `Closes`, `Fixes`, and `Resolves` are allowed only for source-only issues
  where PR merge fully satisfies acceptance.
- Related decisions should reference `decisions/` records when applicable.

## 14. Safety Notes Section

Required section:

```markdown
## Safety Notes

- Live GitHub write authorized: no
- Secret exposure risk reviewed: yes/no
- User data exposure risk reviewed: yes/no
- Requires operator approval before apply: yes/no
```

Rules:

- Default live GitHub write authorization is `no`.
- Any `yes` for live write must reference the approving issue/comment/decision.
- Secret-bearing evidence must be redacted before posting.
- If the issue touches auth, DB, UI, or infrastructure architecture, the
  Decision Registry must be checked before implementation.

## 15. Future GitHub Issue Form Blueprint

Future implementation may create:

```text
.github/ISSUE_TEMPLATE/board-work-item.yml
```

Minimum form fields:

| Field | Required | Maps to |
|---|---|---|
| Summary | yes | issue title/context |
| Kind | yes | `Kind` |
| Faz | yes | `Faz` |
| Track | yes | `Track` |
| Priority | yes | `Priority` |
| Owner repo | yes | `Owner repo` |
| SSOT refs | yes | `SSOT refs` |
| Acceptance criteria | yes | `Acceptance Criteria` |
| Evidence plan | yes | `Evidence` |
| Does not prove | yes | `Evidence / Does not prove` |
| Next action | yes | `Next Action` |
| Safety notes | yes | `Safety Notes` |

Default labels for the future form:

```yaml
labels:
  - project-roadmap
```

The future form must not auto-add non-roadmap labels except where the operator
or form logic can deterministically derive them from the selected `Kind`.

## 16. BOG-2A Acceptance

BOG-2A is `REVIEW_READY` when:

- this file exists,
- it defines the issue body section order,
- it defines the `agent-state:v1` block,
- it defines claim and verification metadata,
- it defines evidence and `Does not prove` requirements,
- it defines future Issue Form boundaries without creating the form,
- `BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md` records this contract,
- `SSOT-MAP.md` links this contract,
- write authorization for this docs path passes,
- schema/policy/doc-nav checks still pass,
- no `.github/ISSUE_TEMPLATE`, GitHub issue, GitHub Project, PR, workflow,
  label, or source/runtime mutation was made.

BOG-2A is not live-active until a separate implementation step creates an issue
form after operator approval and dry-run verification.
