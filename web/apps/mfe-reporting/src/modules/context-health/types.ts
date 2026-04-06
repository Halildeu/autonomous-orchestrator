export type { KpiResult, ChartResult, ChartDataRow } from '../dashboard/types';

export type GridColumnDef = {
  field: string;
  headerName: string;
  type: 'text' | 'number' | 'badge' | 'date';
  width: number;
};

export type GridMeta = {
  gridId: string;
  title: string;
  columns: GridColumnDef[];
};

export type ContextHealthStatus = {
  enabled: boolean;
  dataDir: string;
  indexDir: string;
  lastRefresh: string;
  fileCount: number;
  overallStatus: string;
};
