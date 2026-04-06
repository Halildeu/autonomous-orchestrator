import React from 'react';
import type { ReportModule } from '../types';

const ContextHealthDashboard = React.lazy(() => import('./ContextHealthDashboard'));

type EmptyFilters = Record<string, never>;

export const contextHealthModule: ReportModule<EmptyFilters, never> = {
  id: 'context-health',
  sharedReportId: 'context-health' as never,
  route: 'context-health',
  titleKey: 'Context Health',
  descriptionKey: 'AI Context Orchestration health monitoring dashboard',
  breadcrumbKeys: [{ key: 'Reports', to: '/reports' }, { key: 'Context Health' }],
  navKey: 'Context Health',
  createInitialFilters: () => ({}) as EmptyFilters,
  renderFilters: () => null,
  getColumns: () => [],
  fetchRows: async () => ({ rows: [], total: 0 }),
  renderDashboard: () =>
    React.createElement(
      React.Suspense,
      { fallback: React.createElement('div', { className: 'animate-pulse h-96 bg-surface-muted rounded-lg' }) },
      React.createElement(ContextHealthDashboard),
    ),
};
