import js from '@eslint/js';
import css from '@eslint/css';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import { rules as semanticThemeRules } from './scripts/lint/eslint-plugin-semantic-theme.mjs';
import { rules as cssVarFallbackRules } from './scripts/lint/eslint-plugin-css-var-fallback.mjs';
import { rules as noAntImportRules } from './scripts/lint/eslint-plugin-no-ant-import.mjs';

/**
 * Downgrade all "error"-level rules from recommended configs to "warn" so
 * pre-existing violations are captured by --max-warnings instead of causing
 * an immediate exit-code 1.  Explicit overrides below can still promote
 * individual rules back to "error" (e.g. no-ant-import).
 */
function downgradeErrorsToWarn(...configs) {
  const map = {};
  for (const cfg of configs) {
    const items = Array.isArray(cfg) ? cfg : [cfg];
    for (const item of items) {
      if (!item.rules) continue;
      for (const [rule, level] of Object.entries(item.rules)) {
        const severity = Array.isArray(level) ? level[0] : level;
        if (severity === 'error' || severity === 2) {
          map[rule] = Array.isArray(level) ? ['warn', ...level.slice(1)] : 'warn';
        }
      }
    }
  }
  return map;
}

const recommendedWarnOverrides = downgradeErrorsToWarn(
  js.configs.recommended,
  ...tseslint.configs.recommended,
);

export default tseslint.config(
  {
    ignores: [
      'dist',
      'apps/**/dist/**',
      'apps/**/dist-quality/**',
      'packages/**/dist/**',
      'archive/**',
      'storybook-static',
      '.storybook/**',
      'reports',
      'coverage',
      'security-reports',
      'tests/smoke/**/*.mjs',
      'node_modules',
      '**/node_modules/**',
      '**/node_modules_old/**',
      'node_modules_failed_pnpm/**',
      'node_modules_failed_pnpm_hoisted/**',
      '**/webpack.*.js',
      '**/webpack.*.ts',
      '**/tailwind.config.*',
      '**/.stylelintrc.*',
      '**/jest.config.*',
      '**/babel.config.*',
      '**/postcss.config.*',
      'storybook.config.mjs',
      '**/*.stories.{ts,tsx}',
      '**/*.figma.{ts,tsx}',
      'scripts/ops/**',
      // Packages with eslint-disable comments referencing unloaded plugins (react-hooks, jsx-a11y)
      'packages/x-kanban/**',
      'packages/x-editor/**',
      '.__mf__temp/**',
      '**/.__mf__temp/**',
      '.mf/**',
      'scripts/theme/**',
    ],
  },
  /* ---- Linter options ---- */
  {
    linterOptions: {
      reportUnusedDisableDirectives: 'warn',
    },
  },
  /* ---- JS/TS rules — scoped to non-CSS files only ---- */
  {
    files: ['**/*.{ts,tsx,js,jsx,mjs}'],
    ...js.configs.recommended,
  },
  ...tseslint.configs.recommended.map((cfg) => ({
    ...cfg,
    files: cfg.files ?? ['**/*.{ts,tsx,js,jsx,mjs}'],
  })),
  {
    files: ['**/*.{ts,tsx,js,jsx,mjs}'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2025,
      },
    },
    plugins: {
      'semantic-theme': { rules: semanticThemeRules },
      'css-var-fallback': { rules: cssVarFallbackRules },
      'no-ant-import': { rules: noAntImportRules },
    },
    rules: {
      // Bulk-downgrade all recommended error-level rules to warn so
      // --max-warnings governs the exit code instead of any single error.
      ...recommendedWarnOverrides,
      // Custom plugin rules
      'semantic-theme/no-inline-color-literals': 'warn',
      // Disabled: conflicts with check_no_hardcoded_theme_styles (fallback hex = violation).
      // Token system is reliable — var(--token) without fallback is the correct pattern.
      'css-var-fallback/no-css-var-without-fallback': 'off',
      'no-ant-import/no-new-ant-import': 'error',
      // Targeted overrides (options or off)
      // TS handles unused vars — disable vanilla rule to avoid double-counting
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
        destructuredArrayIgnorePattern: '^_',
        ignoreRestSiblings: true,
      }],
      'no-undef': 'off', // Too many false positives with TS global types
      'no-unused-private-class-members': 'warn',
    },
  },
  /* ---- @eslint/css — native CSS linting (ESLint 9+) ---- */
  {
    files: ['**/*.css'],
    ignores: [
      '**/dist/**',
      '**/node_modules/**',
      '**/coverage/**',
      /* Auto-generated files — read-only */
      '**/tokens/build/**',
      '**/styles/theme.css',
      '**/styles/generated-theme-inline.css',
      'apps/mfe-shell/src/index.css',
    ],
    plugins: { css },
    language: 'css/css',
    rules: {
      'css/no-invalid-at-rules': 'off', // False positives on Tailwind v4 @theme, @apply, etc.
      'css/no-invalid-properties': 'off', // False positives on CSS custom properties (--var)
      'css/no-duplicate-imports': 'error',
    },
  },
  {
    files: [
      '**/__tests__/**/*.{ts,tsx,js,jsx}',
      '**/*.{spec,test}.{ts,tsx,js,jsx}',
      'tests/**/*.{ts,tsx,js,jsx}',
      'docs/tests/**/*.{ts,tsx,js,jsx}',
    ],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
);
