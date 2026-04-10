# AGENT-CODEX.md — Codex-Specific Rules

This file extends AGENTS.md with Codex-specific guidance. AGENTS.md is the canonical source; this file adds Codex self-audit checklists.

## Test Quality Self-Audit Checklist

Before generating or modifying any test file, answer these 5 questions:

1. **Prod symbol import?** Does this test file import the actual component/function it claims to test? If the filename is `Button.test.tsx`, is there an `import { Button }` statement?

2. **Interaction or state transition?** Does the test trigger at least one user interaction (fireEvent, userEvent) or verify a state transition? If not, this is a shallow render test.

3. **Tautological assertion?** Are any assertions always-true regardless of component behavior? `expect(true).toBe(true)`, `expect(wrapper).toBeDefined()` alone = tautological.

4. **Duplicate body?** Is this test body structurally identical to another test file? If so, extract shared utilities and write unique scenarios.

5. **Why is this test necessary?** What specific behavior does this test verify that no other test covers? If you cannot articulate the unique value, do not create the test.

## Cross-Agent MUST Rules (from AGENTS.md)

- Do NOT generate UI tests without component or prod symbol import evidence
- Zero tolerance for bulk markers: quality-edge-boost, auto-generated-test, test-scaffold
- data-testid is last resort — prefer semantic queries (getByRole, getByText, getByLabelText)
- Mock-heavy tests (>3 mocks) MUST have at least one real contract or side-effect assertion
- Batch test generation MUST include dedup and self-check before commit
