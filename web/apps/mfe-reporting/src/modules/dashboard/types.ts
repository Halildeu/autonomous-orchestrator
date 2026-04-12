export type DashboardListItem = {
  key: string;
  title: string;
  description: string;
  category: string;
  icon: string;
  timeRanges: string[];
  defaultTimeRange: string;
  kpiCount: number;
  chartCount: number;
  /** CNS-006 R18: reportGroup for deny-default filtering */
  reportGroup?: string;
};

export type LayoutSection = {
  type: 'kpi-strip' | 'chart-row';
  ids: string[];
};

export type LayoutConfig = {
  sections: LayoutSection[];
};

export type KpiMeta = {
  id: string;
  title: string;
  format: string;
};

export type ChartMeta = {
  id: string;
  title: string;
  chartType: string;
  size: string;
};

export type DashboardMetadata = {
  key: string;
  title: string;
  description: string;
  category: string;
  icon: string;
  timeRanges: string[];
  defaultTimeRange: string;
  layout: LayoutConfig;
  kpis: KpiMeta[];
  charts: ChartMeta[];
};

export type TrendDto = {
  direction: 'up' | 'down' | 'stable';
  percentage: number;
};

export type BenchmarkDto = {
  label: string;
  value: number | null;
};

export type DrillToDto = {
  reportKey: string;
  filters?: Record<string, unknown>;
  filterColumn?: string;
  filterFromField?: string;
};

export type KpiResult = {
  id: string;
  title: string;
  format: string;
  value: unknown;
  formattedValue: string;
  trend: TrendDto | null;
  tone: string;
  benchmark: BenchmarkDto | null;
  drillTo: DrillToDto | null;
};

export type ChartDataRow = {
  label: string;
  value: number;
  [key: string]: unknown;
};

export type ChartResult = {
  id: string;
  title: string;
  chartType: 'bar' | 'line' | 'pie' | 'area';
  size: string;
  data: ChartDataRow[];
  chartConfig: Record<string, unknown>;
  drillTo: DrillToDto | null;
};
