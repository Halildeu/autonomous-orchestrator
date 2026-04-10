---
globs: web/**/*.test.tsx,web/**/*.test.ts,web/**/*.spec.tsx,web/**/*.spec.ts
---
# Frontend Test Quality Rules

Policy ref: `policies/policy_test_quality.v1.json`
Semgrep: EP-006 (shallow render), EP-007 (tautological), EP-008 (marker ban), EP-009 (data-testid render)

## Component Test Requirements

- Use `@testing-library/react` with userEvent or fireEvent — every component test MUST trigger at least one interaction
- Query priority: `getByRole` > `getByText` > `getByLabelText` > `getByTestId` — data-testid is last resort, not default strategy
- Every test MUST import the actual component being tested (filename must match import)
- Every test MUST have at least 2 meaningful assertions beyond DOM existence

## Mock Boundaries

- Mock: external API calls, router, global state providers
- Do NOT mock: internal component logic, child components (unless deeply nested), CSS/styling
- If vi.mock/jest.mock count > 3, at least one assertion must verify a real side effect (API call payload, state change, callback params)

## Prohibited Patterns

- Shallow render + toBeInTheDocument only (EP-006)
- expect(true).toBe(true) or any tautological (EP-007)
- quality-edge-boost / auto-generated-test markers (EP-008)
- data-testid render + toBeInTheDocument + zero interaction (EP-009)
- Template duplication across files (TQ-003: normalized body hash check)
