import React, { useMemo } from 'react';
import { SmartDashboard } from '@mfe/design-system';
import type { DashboardWidget } from '@mfe/design-system';
import { useContextHealthData } from './useContextHealthData';
import StatusBadge from './StatusBadge';
import HealthComponentBar from './charts/HealthComponentBar';
import SectionStatusPie from './charts/SectionStatusPie';
import DocGraphBar from './charts/DocGraphBar';
import ProjectDistributionBar from './charts/ProjectDistributionBar';
import ProviderCapabilitiesBar from './charts/ProviderCapabilitiesBar';
import WorkIntakeBar from './charts/WorkIntakeBar';
import BenchmarkGapsBar from './charts/BenchmarkGapsBar';
import GridTabPanel from './grids/GridTabPanel';
import SessionPanel from './SessionPanel';

const ContextHealthDashboard: React.FC = () => {
  const {
    status,
    session,
    kpis,
    charts,
    grids,
    activeGridId,
    gridData,
    loading,
    error,
    autoRefresh,
    refresh,
    selectGrid,
    toggleAutoRefresh,
  } = useContextHealthData();

  const widgets: DashboardWidget[] = useMemo(
    () =>
      kpis.map((kpi) => ({
        key: kpi.id,
        title: kpi.title,
        type: 'kpi' as const,
        value: kpi.formattedValue,
        trend: kpi.trend
          ? { direction: kpi.trend.direction as 'up' | 'down' | 'stable', percentage: kpi.trend.percentage }
          : undefined,
        tone: (kpi.tone as DashboardWidget['tone']) || 'default',
        size: 'sm' as const,
        pinned: true,
      })),
    [kpis],
  );

  const chartMap = useMemo(() => {
    const map: Record<string, { data: Array<{ label: string; value: number; [k: string]: unknown }> }> = {};
    for (const chart of charts) {
      map[chart.id] = { data: chart.data };
    }
    return map;
  }, [charts]);

  if (loading && kpis.length === 0) {
    return (
      <div className="space-y-4 p-6">
        <div className="h-8 w-64 animate-pulse rounded bg-surface-muted" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (error && kpis.length === 0) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <h3 className="text-sm font-semibold text-red-800">Failed to load Context Health data</h3>
        <p className="mt-1 text-sm text-red-600">{error}</p>
        <button
          onClick={refresh}
          className="mt-3 rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-text-primary">Context Health</h2>
          {status && <StatusBadge status={status.overallStatus} />}
          {status && (
            <span className="text-xs text-text-subtle">
              {status.fileCount} files
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleAutoRefresh}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
              autoRefresh
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-surface-muted text-text-subtle hover:bg-surface-hover'
            }`}
          >
            {autoRefresh && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />}
            Auto-refresh
          </button>
          <button
            onClick={refresh}
            className="rounded-md bg-action-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-action-primary-hover"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Strip */}
      <SmartDashboard widgets={widgets} columns={4} density="compact" />

      {/* Active Session */}
      <SessionPanel session={session} />

      {/* Charts Row 1: Health Components (lg) + Section Status Pie */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Health Score Components</h3>
          {chartMap['health-component-breakdown'] ? (
            <HealthComponentBar data={chartMap['health-component-breakdown'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Section Status Distribution</h3>
          {chartMap['section-status-distribution'] ? (
            <SectionStatusPie data={chartMap['section-status-distribution'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
      </div>

      {/* Charts Row 2: Doc Graph + Project Distribution */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Doc Graph Issues</h3>
          {chartMap['doc-graph-metrics'] ? (
            <DocGraphBar data={chartMap['doc-graph-metrics'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Project & Extension Overview</h3>
          {chartMap['project-distribution'] ? (
            <ProjectDistributionBar data={chartMap['project-distribution'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
      </div>

      {/* Charts Row 3: Provider Capabilities + Work Intake */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">AI Provider Capabilities</h3>
          {chartMap['provider-capabilities'] ? (
            <ProviderCapabilitiesBar data={chartMap['provider-capabilities'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Work Intake Pipeline</h3>
          {chartMap['work-intake-breakdown'] ? (
            <WorkIntakeBar data={chartMap['work-intake-breakdown'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
      </div>

      {/* Charts Row 4: Benchmark + Layer Boundary */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Benchmark & Gaps</h3>
          {chartMap['benchmark-gaps'] ? (
            <BenchmarkGapsBar data={chartMap['benchmark-gaps'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
        <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Repo Hygiene</h3>
          {chartMap['repo-hygiene'] ? (
            <DocGraphBar data={chartMap['repo-hygiene'].data} />
          ) : (
            <div className="h-48 animate-pulse rounded bg-surface-muted" />
          )}
        </div>
      </div>

      {/* Data Grids */}
      <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
        <GridTabPanel
          grids={grids}
          activeGridId={activeGridId}
          gridData={gridData}
          onSelectGrid={selectGrid}
        />
      </div>
    </div>
  );
};

export default ContextHealthDashboard;
