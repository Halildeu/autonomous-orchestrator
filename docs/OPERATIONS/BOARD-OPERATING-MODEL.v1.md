# Board Operating Model (v1)

Status: ACTIVE / product capability v1
Started: 2026-06-17
Scope: governance board discipline for autonomous-orchestrator and managed repos
Current mode: active for autonomous-orchestrator; live GitHub writes remain digest, target, confirmation, and token gated

## 1. Purpose

This document defines how a GitHub Project board is used as an active work
surface without replacing repo SSOT.

The model is adopted from the proven pattern observed in:

- `platform-k8s-gitops`: active issue claim, board status, PR evidence, and
  acceptance discipline.
- `ao-kernel`: repo manifest to GitHub Project one-way mirror, digest binding,
  and drift-check discipline.

The product capability goal is narrow:

- make work visible,
- prevent duplicate multi-session work,
- prevent premature `Done`,
- preserve repo artifacts as authority,
- make the next action obvious to a fresh agent session.

## 2. Authority Boundary

| Surface | Canonical for | Not canonical for |
|---|---|---|
| Repo SSOT files | policy, roadmap, acceptance criteria, schema, evidence references | live board status |
| GitHub Project board | active work status, open risk/issue/gate visibility, acceptance queue | architecture, runtime truth, release authority |
| GitHub issue body | item-local handoff state, claim state, next action | global roadmap truth |
| GitHub issue comments | append-only progress/evidence/audit log | editable current state |
| PR body | source delta summary and `Tracked by` relation | runtime acceptance |
| CI/workflows | mechanical checks and source-ready evidence | final business acceptance |

Hard boundary:

- Board state does not override repo SSOT.
- Repo SSOT does not silently close board work.
- PR merge does not imply `Done` unless the item is source-only and explicitly
  safe to close.
- Live/acceptance evidence must be recorded before a runtime or governance
  item is marked `Done`.

## 3. Board Is Curated

The board is not an intake firehose.

Board-eligible items:

- phase or milestone work,
- gate work,
- risk or RAID items,
- roadmap-visible follow-up work,
- work that needs cross-session handoff,
- source-ready items waiting for runtime or acceptance evidence.

Board-ineligible by default:

- routine small code PRs,
- dependency noise,
- exploratory notes,
- one-off trivial fixes,
- every issue opened in a repo.

Label gate:

- `project-roadmap` means the item may appear on the board.
- Items without this label are not auto-boarded.
- Normal implementation PRs link to a roadmap issue; they do not become board
  items only because they exist.

## 4. Required Fields

The first adopted board must keep the field set small.
The detailed field and label contract is
`docs/OPERATIONS/BOARD-FIELD-LABEL-CONTRACT.v1.md`.

| Field | Required options |
|---|---|
| `Status` | `Backlog`, `Todo`, `In Progress`, `Blocked`, `Needs Verify`, `Done` |
| `Faz` | project-specific phase names |
| `Track` | `core`, `ops`, `github-ops`, `pm-suite`, `work-intake`, `ui`, `managed-repo` |
| `Priority` | `P0`, `P1`, `P2`, `P3` |
| `Kind` | `umbrella`, `milestone`, `gate`, `risk`, `issue` |

Minimum label set:

- `project-roadmap`
- `risk`
- `gate`
- `needs-verification`
- `blocked`
- `security`
- `quality`

Adoption rule:

- A roadmap-visible item is not fully tracked until `Status`, `Faz`, `Track`,
  `Priority`, and `Kind` are all populated.

## 5. Status Semantics

| Status | Meaning | Claimable |
|---|---|---|
| `Backlog` | Captured but not triaged | No |
| `Todo` | Triage complete and ready for work | Yes |
| `In Progress` | Claimed by an active session | No, unless claim is stale |
| `Blocked` | Waiting on an external dependency or prior gate | No |
| `Needs Verify` | Source-ready or merged; runtime/acceptance evidence pending | No |
| `Done` | Acceptance complete and issue deliberately closed | No |

Hard rules:

- `Kind=umbrella` is never claimable.
- `Backlog` must be triaged before claim.
- `Needs Verify` is an acceptance queue, not closure.
- `Done` requires deliberate close plus evidence.
- `needs-verification` label blocks closure.
- `Blocked` requires both board status and a `BLOCKED` comment.

## 6. Issue Body Contract

Every executable board issue must carry an `agent-state:v1` block.
The detailed issue body and future Issue Form contract is
`docs/OPERATIONS/BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md`.

```markdown
## Agent State

<!-- agent-state:v1
status: todo
claim_session: none
claim_worktree: none
claim_branch: none
claim_updated_at: none
expires_at: none
-->

**Faz:** <phase>
**Track:** <track>
**Priority:** <P0|P1|P2|P3>
**Kind:** issue
**Owner repo:** <owner/repo>

### Context
<why this work exists; linked policy/roadmap/gate/risk>

### Current Claim
<active session/worktree/branch or "unclaimed">

### Evidence
- Source:
- Desired-state:
- Runtime/live:
- Browser/user-path:
- Does not prove:

### Remaining
<blockers, open work, non-blocking follow-ups>

### Next Action
<the first concrete action for a fresh session>

### Related PRs
<PR links or "none">
```

The issue body is the current handoff surface. Comments remain append-only
audit evidence.

## 7. Comment Taxonomy

| Prefix | Use |
|---|---|
| `CLAIM` | session claims an item |
| `HEARTBEAT` | session extends claim lease |
| `PROGRESS` | meaningful progress checkpoint |
| `EVIDENCE` | source, desired-state, runtime, browser, or acceptance evidence |
| `HANDOFF` | session releases or transfers work |
| `BLOCKED` | blocker plus unblock owner/action |
| `READY-FOR-VERIFY` | source-ready; acceptance pending |
| `DONE-CANDIDATE` | evidence appears complete; closure may be reviewed |

## 8. Claim-Before-Work

Important or multi-step work must be claimed before implementation begins.

Claim identity is not the assignee. Multiple sessions may use the same GitHub
user. The claim identity is the `CLAIM` comment plus `agent-state:v1`.

Claim protocol:

1. Select an eligible issue.
2. Post `CLAIM session=<id> worktree=<path> branch=<branch> at=<iso> expires=<iso>`.
3. Re-read all comments.
4. Compute the earliest active claim.
5. If this session wins, update issue body and board `Status=In Progress`.
6. If this session loses, post `HANDOFF released=lost-race` and choose another item.
7. Use `HEARTBEAT` for long-running work.
8. Expired claims may be reclaimed.

This prevents two active sessions from doing the same expensive work.

## 9. PR Linking Rule

The detailed PR body and future Pull Request Template contract is
`docs/OPERATIONS/BOARD-PR-TEMPLATE-CONTRACT.v1.md`.

Default for runtime, GitOps, acceptance, or governance work:

```markdown
Tracked by #123
Runtime evidence pending
```

Avoid:

```markdown
Closes #123
Fixes #123
Resolves #123
```

`Closes/Fixes/Resolves` is allowed only for source-only issues where PR merge
itself fully satisfies the acceptance criteria.

PR merge effect:

- source-ready evidence is recorded,
- board status moves to `Needs Verify`,
- claim is cleared,
- runtime/acceptance evidence remains pending.

PR merge must not auto-produce `Done` for runtime or governance items.

## 10. Evidence Taxonomy

Every item should separate evidence into these layers:

| Layer | Meaning |
|---|---|
| Source | code, schema, docs, or manifest merged |
| Desired-state | GitOps/config target declares the intended state |
| Runtime/live | live process, service, job, cluster, API, or artifact observed |
| Browser/user-path | user-facing path verified through the actual UX where applicable |

`Does not prove` is mandatory. It records what remains unproven and prevents
closure overclaim.

## 11. Automation Boundary

The detailed minimal board tooling design is
`docs/OPERATIONS/BOARD-SCRIPT-DESIGN.v1.md`.

Machine-readable governance contracts:

- `policies/policy_board_governance.v1.json`
- `schemas/policy-board-governance.schema.v1.json`
- `schemas/board-projection.schema.v1.json`

Allowed initial automation:

- list eligible work,
- claim/release/heartbeat,
- mark merged PR as `Needs Verify`,
- capture backlog items,
- report board/body drift.

Not allowed in initial automation:

- auto-close runtime issues,
- auto-mark `Done`,
- mutate repo SSOT,
- create broad board firehose ingestion,
- run live GitHub writes without explicit token and operator boundary,
- treat board state as release authority.

## 12. Adoption Boundary

This model is not active simply because this file exists.

Activation requires:

1. board field contract approved,
2. label gate approved,
3. issue template approved,
4. PR template approved,
5. script dry-run tests passing,
6. GitHub token/PAT behavior documented,
7. rollout recorded in the adoption plan.

Until then, this document is an adoption candidate and planning authority only.
