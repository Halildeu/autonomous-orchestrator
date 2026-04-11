/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  // ── Plugin Resolution (pnpm monorepo) ──
  plugins: [
    '@stryker-mutator/vitest-runner',
  ],

  // ── Test Runner ──
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
  },

  // ── Mutation Targets ──
  // Wave 1: Enterprise components (baseline: 8.98%)
  // Wave 3: Logic-heavy primitives (state, events, math)
  // Excluded: Layout primitives (Container, Flex, Grid, Stack) — pure CSS class mapping
  mutate: [
    'src/enterprise/**/*.tsx',
    // Wave 3: Logic-heavy primitives (sorted by LoC)
    'src/primitives/popover/Popover.tsx',         // 545 lines — positioning, portal, events
    'src/primitives/modal/Modal.tsx',             // 306 lines — focus trap, escape, backdrop
    'src/primitives/dialog/Dialog.tsx',           // 275 lines — native dialog, focus management
    'src/primitives/input/Input.tsx',             // 283 lines — controlled/uncontrolled, validation
    'src/primitives/checkbox/Checkbox.tsx',       // 272 lines — indeterminate, group state
    'src/primitives/radio/Radio.tsx',             // 270 lines — group selection, keyboard nav
    'src/primitives/button/Button.tsx',           // 268 lines — loading, disabled, icon variants
    'src/primitives/progress/Progress.tsx',       // 262 lines — math (circumference, dashOffset)
    'src/primitives/select/Select.tsx',           // 250 lines — dropdown, keyboard nav, controlled
    'src/primitives/switch/Switch.tsx',           // ~180 lines — toggle state, form integration
    // Exclusions
    '!src/**/__tests__/**',
    '!src/**/index.ts',
    '!src/**/types.ts',
  ],

  // ── Mutation Operators ──
  // Focus on meaningful mutations, skip cosmetic ones
  mutator: {
    excludedMutations: [
      'StringLiteral',     // CSS class changes = noise
      'ObjectLiteral',     // Default props = noise
    ],
  },

  // ── Performance ──
  concurrency: 4,
  timeoutMS: 30000,
  incremental: true,  // Only re-test changed files
  incrementalFile: '.stryker-cache/incremental.json',

  // ── Reporting ──
  reporters: ['html', 'clear-text', 'progress'],
  htmlReporter: {
    fileName: 'reports/mutation/index.html',
  },

  // ── Thresholds ──
  // Wave 3: expanded scope (enterprise + 10 primitives)
  // Baseline TBD after first run with expanded scope
  // Target: raise to 30% via surviving mutant analysis
  thresholds: {
    high: 80,     // Green: 80%+ mutations killed
    low: 30,      // Yellow: 30-80%
    break: 20,    // CI fails below 20% (lowered for expanded scope)
  },

  // ── Coverage Analysis ──
  coverageAnalysis: 'perTest',  // Map each test to the mutants it can kill

  // ── Ignore Patterns ──
  ignorePatterns: [
    'dist',
    'node_modules',
    '.stryker-cache',
    'reports',
    '**/*.stories.*',
    '**/*.visual.*',
    '**/*.browser.*',
  ],
};
