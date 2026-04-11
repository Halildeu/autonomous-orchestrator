import { defineWorkspace } from 'vitest/config';

export default defineWorkspace([
  'packages/auth/vitest.config.ts',
  'packages/design-system/vitest.config.ts',
  'packages/x-charts/vitest.config.ts',
  'packages/x-data-grid/vitest.config.ts',
  'packages/x-editor/vitest.config.ts',
  'packages/x-form-builder/vitest.config.ts',
  'packages/x-kanban/vitest.config.ts',
  'packages/x-scheduler/vitest.config.ts',
  'packages/blocks/vitest.config.ts',
  'apps/mfe-shell/vitest.config.ts',
  'apps/mfe-audit/vitest.config.ts',
  'apps/mfe-access/vitest.config.ts',
  'apps/mfe-users/vitest.config.ts',
]);
