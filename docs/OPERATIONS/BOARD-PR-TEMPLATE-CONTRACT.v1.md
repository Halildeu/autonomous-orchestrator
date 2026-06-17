# Board PR Template Contract (v1)

Status: REVIEW_READY
Started: 2026-06-17
Scope: BOG-2B PR body and future Pull Request Template contract
Current mode: docs-only; no `.github/PULL_REQUEST_TEMPLATE`, GitHub PR, issue, Project, workflow, label, or source/runtime mutation is authorized by this document alone

## 1. Purpose

This contract defines how pull requests should link to board-visible work
without prematurely closing governance, runtime, GitOps, or acceptance issues.

The core rule is:

```text
Use Tracked by for board-visible work unless PR merge alone fully satisfies the issue.
```

## 2. Applicability

This contract applies to PRs that touch:

- board governance work,
- roadmap-visible work,
- runtime/GitOps desired state,
- acceptance or verification gates,
- issue/PR/Project automation,
- source changes linked to a `project-roadmap` issue.

Routine source-only PRs may use normal close keywords only when PR merge fully
satisfies the issue acceptance criteria and no runtime/user acceptance remains.

## 3. Required PR Body Sections

Every board-linked PR must include these sections:

1. `Summary`
2. `Board Relation`
3. `Evidence`
4. `Risk and Rollback`
5. `Merge Effect`
6. `Checklist`

Future scripts should parse these headings, not free-form prose.

## 4. Summary Section

Required section:

```markdown
## Summary

- <one concise source delta>
- <one concise behavior/governance effect>
- <one explicit boundary, if relevant>
```

The summary must distinguish source changes from runtime or acceptance outcome.

## 5. Board Relation Section

Required section:

```markdown
## Board Relation

Tracked by #<issue>

Close keyword allowed: no
Reason: runtime/governance/acceptance evidence remains pending
```

Default relation:

```markdown
Tracked by #123
```

Avoid by default:

```markdown
Closes #123
Fixes #123
Resolves #123
```

Close keywords are allowed only when all conditions are true:

- the issue is source-only,
- the PR fully satisfies every acceptance criterion,
- no `needs-verification` label is present,
- no runtime/live evidence remains pending,
- no user-path acceptance remains pending,
- the PR body states `Close keyword allowed: yes` and explains why.

If any condition is false or unknown, use `Tracked by`.

## 6. Evidence Section

Required section:

```markdown
## Evidence

### Source
- <files, tests, schemas, docs, or generated artifacts>

### Desired-state
- <declared target state or "not applicable">

### Runtime/live
- <runtime proof or "pending after merge">

### Browser/user-path
- <user-path proof or "pending after merge">

### Does not prove
- <what remains unverified>
```

Rules:

- `Does not prove` is mandatory.
- If runtime/live is pending, the linked issue must move to or remain
  `Needs Verify` after merge.
- If browser/user-path is pending, the linked issue must not close on merge.
- Evidence must be inspectable: file path, command, test output, run ID, PR
  check, screenshot path, or report path.
- Do not include secrets, tokens, private contact data, or token-bearing URLs.

## 7. Risk and Rollback Section

Required section:

```markdown
## Risk and Rollback

Risk level: <P0|P1|P2|P3>
Rollback: <revert/disable/config restore/manual rollback>
Side effects: <none/draft/pr/project/issue/workflow/runtime>
```

Rules:

- `Side effects` must be explicit.
- If side effects include `project`, `issue`, `workflow`, or `runtime`, the PR
  must use `Tracked by`; close keywords are not allowed by default.
- Rollback must be concrete enough for a different operator to perform.

## 8. Merge Effect Section

Required section:

```markdown
## Merge Effect

On merge, linked board issue should move to: Needs Verify
Issue close on merge: no
Post-merge evidence required:
- <runtime/live/browser/user-path evidence>
```

Allowed values for `linked board issue should move to`:

| Value | Use |
|---|---|
| `Needs Verify` | source-ready; runtime or acceptance pending |
| `Done Candidate` | evidence appears complete; issue closure still deliberate |
| `No board state change` | PR does not affect board-visible item state |
| `Close via keyword` | source-only issue, all acceptance completed |

Default for governance, runtime, GitOps, Project, issue, and workflow work:

```text
Needs Verify
```

PR merge must not auto-produce `Done` for runtime or governance items.

## 9. Checklist Section

Required section:

```markdown
## Checklist

- [ ] I used `Tracked by` for board-visible runtime/governance/acceptance work.
- [ ] I avoided `Closes/Fixes/Resolves` unless this is source-only complete work.
- [ ] I separated source evidence from runtime/live evidence.
- [ ] I filled `Does not prove`.
- [ ] I checked that no secret or token-bearing evidence is pasted.
- [ ] I listed post-merge verification if `Needs Verify` remains.
```

The checklist is not proof by itself. It is a prompt to make missing evidence
visible.

## 10. Future Pull Request Template Blueprint

Future implementation may create:

```text
.github/PULL_REQUEST_TEMPLATE.md
```

Minimum template:

```markdown
## Summary

-

## Board Relation

Tracked by #

Close keyword allowed: no
Reason:

## Evidence

### Source
-

### Desired-state
-

### Runtime/live
- pending after merge

### Browser/user-path
- pending after merge

### Does not prove
-

## Risk and Rollback

Risk level:
Rollback:
Side effects:

## Merge Effect

On merge, linked board issue should move to:
Issue close on merge:
Post-merge evidence required:
-

## Checklist

- [ ] I used `Tracked by` for board-visible runtime/governance/acceptance work.
- [ ] I avoided `Closes/Fixes/Resolves` unless this is source-only complete work.
- [ ] I separated source evidence from runtime/live evidence.
- [ ] I filled `Does not prove`.
- [ ] I checked that no secret or token-bearing evidence is pasted.
- [ ] I listed post-merge verification if `Needs Verify` remains.
```

This blueprint is not active until a later implementation step creates the
template file and passes validation.

## 11. Drift and Enforcement Hooks

Later dry-run tooling should report:

- board-linked PR without `Tracked by`,
- forbidden `Closes`, `Fixes`, or `Resolves` on runtime/governance issues,
- missing `Does not prove`,
- missing post-merge verification when merge effect is `Needs Verify`,
- PR body says close keyword allowed but linked issue still has
  `needs-verification`,
- PR body claims runtime evidence but no inspectable artifact is referenced.

The first enforcement mode must be report-only. Blocking behavior requires a
separate CHG/DCP-style decision and tests.

## 12. BOG-2B Acceptance

BOG-2B is `REVIEW_READY` when:

- this file exists,
- it defines `Tracked by` as the default relation,
- it defines the close-keyword exception,
- it defines PR evidence sections and `Does not prove`,
- it defines merge effect semantics,
- it defines a future PR template blueprint without creating the template,
- `BOARD-GOVERNANCE-ADOPTION-PLAN.v1.md` records this contract,
- `SSOT-MAP.md` links this contract,
- write authorization for this docs path passes,
- schema/policy/doc-nav checks still pass,
- no `.github/PULL_REQUEST_TEMPLATE`, GitHub PR, issue, GitHub Project,
  workflow, label, or source/runtime mutation was made.

BOG-2B is not live-active until a separate implementation step creates a PR
template after operator approval and validation.
