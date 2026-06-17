# Board Field and Label Contract (v1)

Status: REVIEW_READY
Started: 2026-06-17
Scope: BOG-1A minimal GitHub Project field and label contract
Current mode: docs-only; no GitHub Project, issue, PR, workflow, or source/runtime mutation is authorized by this document alone

## 1. Purpose

This contract defines the smallest board field and label set needed to make
roadmap-visible work trackable without turning the board into SSOT or intake.

It supports these operating goals:

- make active work visible,
- make claim state and acceptance state explicit,
- prevent broad auto-ingestion,
- prevent premature `Done`,
- keep repo SSOT files authoritative.

## 2. Applicability

This contract applies only to board-eligible GitHub issues that carry the
`project-roadmap` label.

It does not apply to:

- every issue in the repo,
- every PR in the repo,
- routine dependency or maintenance noise,
- source-only issues that do not need cross-session tracking,
- artifacts that are better tracked only in repo SSOT files.

Normal PRs should link to board issues. They do not become board items only
because they exist.

## 3. Required Project Fields

Every board item must have all five fields populated.

| Field | Type | Required values |
|---|---|---|
| `Status` | single select | `Backlog`, `Todo`, `In Progress`, `Blocked`, `Needs Verify`, `Done` |
| `Faz` | single select | `F0 Written Boundary`, `F1 Board Contract`, `F2 Issue PR Contract`, `F3 Board Script`, `F4 PR Evidence`, `F5 Projection Drift`, `FZ Managed Repo` |
| `Track` | single select | `core`, `ops`, `github-ops`, `pm-suite`, `work-intake`, `ui`, `managed-repo` |
| `Priority` | single select | `P0`, `P1`, `P2`, `P3` |
| `Kind` | single select | `umbrella`, `milestone`, `gate`, `risk`, `issue` |

Field creation is not authorized by this document. BOG-1B must choose whether
these fields are applied to a new GitHub Project or an existing Project.

## 4. Status Contract

| Status | Meaning | Allowed entry | Exit condition | Claimable |
|---|---|---|---|---|
| `Backlog` | Captured but not triaged | manual capture or gated backlog script | triage fills fields and next action | No |
| `Todo` | Ready for work | triage complete, no active claim | valid `CLAIM` wins race | Yes |
| `In Progress` | Claimed by an active session | valid `CLAIM` plus body update | release, stale claim, blocked, or ready-for-verify | No |
| `Blocked` | Waiting on external decision, dependency, or prior gate | `BLOCKED` comment with unblock owner/action | blocker cleared and item is re-triaged | No |
| `Needs Verify` | Source-ready or merged; acceptance evidence pending | PR/source evidence exists, runtime/user acceptance pending | acceptance evidence recorded or returned to work | No |
| `Done` | Accepted and deliberately closed | evidence complete, no open verification label | terminal unless reopened by operator | No |

Hard rules:

- `Backlog` is not claimable.
- `Kind=umbrella` is not claimable.
- `In Progress` requires a current claim in `agent-state:v1`.
- `Blocked` requires both board status and `blocked` label.
- `Needs Verify` requires `needs-verification` label.
- `Done` requires issue close plus evidence. Board status alone is not enough.
- PR merge must not auto-mark runtime or governance work `Done`.

## 5. Faz Contract

`Faz` is the planning lane for the board adoption path.

| Faz | Use |
|---|---|
| `F0 Written Boundary` | operating model, adoption plan, authority boundary |
| `F1 Board Contract` | field/label contract and target board decision |
| `F2 Issue PR Contract` | issue body, comments, PR body, `Tracked by` semantics |
| `F3 Board Script` | local dry-run/live-gated board commands |
| `F4 PR Evidence` | merge evidence workflow and `Needs Verify` automation |
| `F5 Projection Drift` | manifest projection, drift report, operator-bound sync |
| `FZ Managed Repo` | managed-repo item whose phase is owned by another repo contract |

Do not invent ad hoc `Faz` values during execution. If a new phase is needed,
record it as a plan revision or CHG/DCP-style proposal first.

## 6. Track Contract

| Track | Use |
|---|---|
| `core` | core repo schemas, policies, roadmaps, source guardrails |
| `ops` | local ops commands, workspace reports, fail-closed operational flow |
| `github-ops` | GitHub Project, issue, PR, workflow, and token boundary work |
| `pm-suite` | project management and portfolio tracking surface |
| `work-intake` | intake, selection, claim, lease, and execution ticket flow |
| `ui` | cockpit, dashboard, browser/user-path surfaces |
| `managed-repo` | managed repo onboarding, parity, standards sync, drift |

Prefer the narrowest track that owns the next action. If a task crosses tracks,
choose the track that owns the acceptance gate and mention secondary tracks in
the issue body.

## 7. Priority Contract

| Priority | Meaning | Typical examples |
|---|---|---|
| `P0` | blocks safe operation or can corrupt authority/state | wrong SSOT authority, unsafe live write, secret exposure |
| `P1` | blocks planned adoption or a required gate | missing field contract, failing dry-run gate, broken claim protocol |
| `P2` | important but not blocking the current gate | reporting gap, ergonomics gap, non-critical drift |
| `P3` | cleanup, polish, or optional improvement | wording, small docs refinement, future automation idea |

Priority must describe operational impact, not preference.

## 8. Kind Contract

| Kind | Use | Claimable |
|---|---|---|
| `umbrella` | parent grouping issue; cannot be directly implemented | No |
| `milestone` | phase-level outcome with multiple child issues | No, unless explicitly scoped as a single task |
| `gate` | pass/fail criterion or readiness blocker | Yes, if scoped |
| `risk` | RAID/risk item requiring mitigation or decision | Yes, if scoped |
| `issue` | executable work item | Yes |

`umbrella` items must link child issues or checklist entries. They should not
carry active claim state.

## 9. Label Contract

Minimum labels:

| Label | Meaning | Required field relation |
|---|---|---|
| `project-roadmap` | explicit board ingestion gate | item must appear on board or be reported as missing |
| `risk` | risk or RAID item | usually `Kind=risk` |
| `gate` | readiness/check gate | usually `Kind=gate` |
| `needs-verification` | source-ready, acceptance pending | requires `Status=Needs Verify`; blocks closure |
| `blocked` | blocked item | requires `Status=Blocked` and `BLOCKED` comment |
| `security` | security-sensitive item | priority must be reviewed; often `P0` or `P1` |
| `quality` | quality/test/verification item | often `Track=ops`, `core`, or `managed-repo` |

Only `project-roadmap` is an ingestion label. Other labels refine meaning but
must not auto-add items to the board by themselves.

## 10. Consistency Rules

Tracking completeness:

- Any open issue with `project-roadmap` must have all five board fields.
- Any board item without `project-roadmap` is a drift candidate unless manually
  justified.
- Empty `Status`, `Faz`, `Track`, `Priority`, or `Kind` is a tracking gap.

Status and label consistency:

- `Status=Needs Verify` requires `needs-verification`.
- `needs-verification` requires `Status=Needs Verify` unless the item is being
  corrected during the same operation.
- `Status=Blocked` requires `blocked`.
- `blocked` requires `Status=Blocked` unless the item is being corrected during
  the same operation.
- `Status=Done` is invalid while `needs-verification` or `blocked` is present.
- `Kind=umbrella` must not have `Status=In Progress`.

PR relation consistency:

- Runtime, GitOps, governance, and acceptance PRs should use `Tracked by #N`.
- `Closes`, `Fixes`, or `Resolves` is allowed only for source-only issues where
  PR merge fully satisfies acceptance.
- Forbidden close keywords on board-visible runtime/governance items should be
  reported by the later drift checker.

## 11. BOG-1A Acceptance

BOG-1A is `REVIEW_READY` when:

- this file exists,
- `BOARD-OPERATING-MODEL.v1.md` references this contract,
- `BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md` records BOG-1A evidence,
- `SSOT-MAP.md` links this contract,
- schema/policy validation still passes,
- no GitHub Project, issue, PR, workflow, or source/runtime mutation was made.

BOG-1A is not `DONE` until the operator accepts this contract or BOG-1B chooses
the target board and confirms the field names/options can be applied without
breaking an existing board.
