# Board PR Merge Evidence Workflow (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-4A PR merge evidence workflow design  
Current mode: design-only; no `.github/workflows`, GitHub issue, GitHub Project,
PR, label, source/runtime, or live workflow mutation is authorized by this
document alone

## 1. Purpose

This document defines the future workflow that records source-ready evidence
when a pull request linked to board-visible work is merged.

The workflow must keep these boundaries intact:

- PR merge may move eligible work to `Needs Verify`.
- PR merge must not mark runtime, governance, GitOps, or acceptance work `Done`.
- PR merge must not close issues unless the issue is explicitly source-only and
  the PR body allows a close keyword.
- Missing credentials, ambiguous links, malformed PR bodies, or unsafe issue
  state must fail closed.

This is BOG-4A design output. BOG-4B may implement it only after workflow write
authorization and test coverage exist.

## 2. Trigger

Future workflow file, if authorized:

```text
.github/workflows/board-pr-merge-evidence.yml
```

Required trigger:

```yaml
on:
  pull_request:
    types: [closed]
```

Processing rule:

- continue only when `pull_request.merged == true`;
- ignore plain closed/unmerged PRs;
- ignore draft-only state changes;
- ignore PRs without a valid `Tracked by #N` relation.

Security rule:

- prefer `pull_request` over `pull_request_target`;
- do not evaluate untrusted code from the PR branch;
- use checked-in workflow code and event JSON only;
- use least-privilege permissions.

## 3. Minimum Permissions

Report-only mode can run with read permissions only.

Future live mutation mode should request only what it uses:

```yaml
permissions:
  contents: read
  pull-requests: read
  issues: write
```

GitHub ProjectV2 mutation may require an operator-provided token with project
scope. If that token is unavailable, the workflow must still produce a report
and must not create a body/board contradiction.

Forbidden:

- printing tokens,
- printing authorization headers,
- printing raw environment dumps,
- storing token-bearing URLs as evidence,
- running live Project mutation with the default token when ProjectV2 write
  permission is not proven.

## 4. PR Relation Parser

The parser reads only the PR body and should use deterministic line-based
matching.

Accepted relation:

```text
Tracked by #123
```

Recommended regular expression:

```text
(?im)^\s*Tracked\s+by\s+#(?P<issue>[0-9]+)\b
```

Multiple tracked issues:

- allowed only when each issue is listed on a separate `Tracked by #N` line;
- each issue is processed independently;
- one issue failure must not hide another issue failure;
- the workflow summary must report per-issue status.

Ambiguous or unsafe body patterns:

| Pattern | Result |
|---|---|
| no `Tracked by` line | no board action |
| malformed `Tracked by` | `WARN`, no mutation |
| duplicate same issue | de-duplicate, process once |
| more than 10 linked issues | `BLOCKED`, no mutation |
| `Closes/Fixes/Resolves` present with `Close keyword allowed: no` | drift finding |
| `Closes/Fixes/Resolves` present without explicit close allowance | drift finding |

Close-keyword detection:

```text
(?im)^\s*(Closes|Fixes|Resolves)\s+#(?P<issue>[0-9]+)\b
```

The workflow must not rely on close keywords for governance/runtime work.

## 5. Eligible Issue State

The workflow may plan or apply a `Needs Verify` transition only when all of
these are true:

- linked issue exists;
- issue has `project-roadmap`;
- issue body contains parseable `agent-state:v1`;
- issue `Kind` is not `umbrella`;
- issue is open;
- current board status is `Todo`, `In Progress`, or missing/unknown;
- no `blocked` label is present;
- the issue is not already `Done`;
- the issue is not already closed.

Issue states that must not be downgraded:

| Current state | Workflow behavior |
|---|---|
| `Blocked` | append/report evidence only; do not move |
| `Needs Verify` | keep status, append idempotent evidence only |
| `Done` | do not move; report potential stale PR relation |
| closed issue | do not reopen; report contradiction if relation remains active |
| `Kind=umbrella` | do not move; report invalid executable link |

## 6. Evidence Comment Contract

Future live mode should append one idempotent evidence comment per linked issue.

Required hidden marker:

```markdown
<!-- board-pr-merge-evidence:v1 pr=<pr-number> sha=<merge-sha> issue=<issue-number> -->
```

Required visible body:

```markdown
EVIDENCE type=pr-merged status=source-ready pr=#<pr-number> sha=<merge-sha>

Source:
- <merged PR URL>
- <merge commit SHA>
- <workflow run URL or report path>

Desired-state:
- <not applicable or target file paths>

Runtime/live:
- pending after merge

Browser/user-path:
- pending after merge

Does not prove:
- runtime acceptance is complete
- user-path acceptance is complete
- issue is ready to close
```

Idempotency rule:

- before adding a comment, search existing comments for the marker;
- if the marker exists, do not add a duplicate comment;
- if the marker exists but board status is stale, report the stale status and
  plan only the missing status transition.

## 7. Board Transition Contract

Eligible transition:

```text
Todo/In Progress/unknown -> Needs Verify
```

Side effects in future live mode:

- add or keep `needs-verification` label;
- set board `Status=Needs Verify`;
- clear active claim fields in `agent-state:v1` when the current claim is tied
  to the PR branch/session or when the issue is source-ready;
- append idempotent evidence comment.

Forbidden transition:

```text
* -> Done
```

Forbidden issue action:

```text
close issue
```

The workflow may produce a `DONE-CANDIDATE` finding only when evidence appears
complete. It must still require deliberate human/operator close.

## 8. Report Contract

Every run must emit a JSON report as a workflow artifact or workspace report.

Minimum shape:

```json
{
  "version": "v1",
  "workflow": "board-pr-merge-evidence",
  "mode": "report",
  "status": "OK",
  "repo": "owner/name",
  "pr": {
    "number": 123,
    "merged": true,
    "merge_sha": "abc123",
    "base_branch": "main"
  },
  "tracked_issues": [
    {
      "issue": 456,
      "eligible": true,
      "current_status": "In Progress",
      "planned_status": "Needs Verify",
      "evidence_marker": "board-pr-merge-evidence:v1 pr=123 sha=abc123 issue=456",
      "planned_actions": [
        "append_evidence_comment",
        "add_needs_verification_label",
        "set_status_needs_verify",
        "clear_claim"
      ],
      "applied_actions": [],
      "blocked_reasons": []
    }
  ],
  "findings": [],
  "evidence": {
    "source": [],
    "desired_state": [],
    "runtime_live": [],
    "browser_user_path": [],
    "does_not_prove": [
      "Runtime/live acceptance remains pending.",
      "Issue closure remains deliberate."
    ]
  }
}
```

Rules:

- `does_not_prove` must never be empty.
- `applied_actions` must be empty in report/dry-run mode.
- each issue result must stand alone.
- malformed GitHub JSON must produce `ERROR` or `BLOCKED`, never partial live
  mutation.

## 9. Failure Policy

| Failure | Required behavior |
|---|---|
| missing Project token | report-only fallback; no Project mutation |
| missing issue write permission | report-only fallback; no comment/label mutation |
| issue not found | `WARN`, no mutation for that issue |
| issue missing `project-roadmap` | drift finding; no mutation |
| issue body missing `agent-state:v1` | drift finding; no mutation |
| active blocked label | append/report only; do not move |
| GitHub API rate limit | `BLOCKED`, no retry storm |
| malformed event payload | `ERROR`, no mutation |
| duplicate workflow replay | idempotent no-op for existing evidence marker |

The workflow must prefer being incomplete over being inconsistent.

## 10. Test Harness Requirements

BOG-4B implementation must include tests before any live mode is accepted.

Required scenarios:

| Scenario | Expected result |
|---|---|
| merged PR with one valid `Tracked by` issue | planned `Needs Verify` transition |
| closed but unmerged PR | no action |
| no `Tracked by` | no action |
| malformed `Tracked by` | warning, no mutation |
| duplicate linked issue | one planned action |
| forbidden close keyword | drift finding |
| source-only close keyword allowed | no governance warning |
| missing token | report-only fallback |
| existing evidence marker | no duplicate comment |
| issue already `Needs Verify` | keep status, evidence idempotent |
| issue `Done` | no downgrade |
| issue `Blocked` | no move |
| `Kind=umbrella` | blocked finding |

Tests must not need a live GitHub token. Fake event payloads and fake GitHub
responses are required before live mutation is considered.

## 11. BOG-4A Acceptance

BOG-4A is `REVIEW_READY` when:

- this file exists;
- trigger and merge-only condition are specified;
- `Tracked by` parser is specified;
- forbidden close-keyword behavior is specified;
- eligible issue state rules are specified;
- idempotent evidence comment marker is specified;
- `Needs Verify` transition contract is specified;
- missing token/PAT fallback is specified;
- report JSON shape is specified;
- test harness scenarios are specified;
- no `.github/workflows`, GitHub issue, GitHub Project, PR, label,
  source/runtime, or live workflow mutation was made.

BOG-4A is not workflow implementation. BOG-4B must provide the workflow and
tests under an explicit write boundary.
