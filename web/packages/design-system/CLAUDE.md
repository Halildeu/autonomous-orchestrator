# CLAUDE.md — @mfe/design-system

## Test Authoring Rules (MANDATORY for all AI agents)

### NEVER do:
- NEVER render `<div>`, `<span>`, or raw HTML as substitute for the real component
- NEVER use `data-testid` as primary query — prefer `getByRole`, `getByLabelText`, `getByText`
- NEVER add marker comments like `quality-depth-boost`, `quality-edge-boost`, or similar
- NEVER copy-paste identical test bodies across multiple test files
- NEVER create a test file without importing the actual component under test

### ALWAYS do:
- ALWAYS import the real component: `import { Button } from '../Button'`
- ALWAYS render the real component: `render(<Button>Click</Button>)`
- ALWAYS test component-specific behavior (unique props, interactions, state)
- ALWAYS verify the test passes: `npx vitest run <test-file>`

### Test file types:

| Pattern | Purpose | Runner |
|---|---|---|
| `*.contract.test.tsx` | API surface: displayName, ref, access control | `vitest` (main) |
| `*.depth.test.tsx` | Behavior depth: prop combos, state transitions, keyboard | excluded from main |
| `*.browser.test.tsx` | Real browser via Playwright | `vitest --config vitest.browser.config.ts` |
| `*.visual.test.tsx` | Screenshot comparison | Playwright visual |
| `*.test.tsx` | General unit tests | `vitest` (main) |

### depth-keep directive:
- Files with `// depth-keep` are exempt from fake-test detection
- Use for depth tests with non-standard import patterns (barrel, alias, etc.)

### CI gate blocks merge if:
- `.depth.test.tsx` file does not import the component under test
- `quality-depth-boost` or `quality-edge-boost` marker is present
- `<div data-testid>` is rendered without real component import

### Generators:
- Contract tests: `npm run test:generate-contracts`
- Depth tests: `npm run test:generate-depth`
- Missing test report: `npm run test:missing-depth`
- Fake test scan: `npm run test:cleanup-fakes`
