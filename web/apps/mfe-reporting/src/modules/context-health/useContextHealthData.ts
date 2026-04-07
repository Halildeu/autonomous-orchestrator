import { useState, useEffect, useCallback, useRef } from 'react';
import type { KpiResult, ChartResult, GridMeta, ContextHealthStatus } from './types';
import {
  fetchContextHealthStatus,
  fetchContextHealthKpis,
  fetchContextHealthCharts,
  fetchContextHealthGrids,
  fetchContextHealthGridData,
  fetchContextHealthSession,
  triggerRefresh,
} from './api';

export interface UseContextHealthDataReturn {
  status: ContextHealthStatus | null;
  session: Record<string, unknown> | null;
  kpis: KpiResult[];
  charts: ChartResult[];
  grids: GridMeta[];
  activeGridId: string | null;
  gridData: Record<string, unknown>[];
  loading: boolean;
  error: string | null;
  autoRefresh: boolean;
  refresh: () => void;
  selectGrid: (gridId: string) => void;
  toggleAutoRefresh: () => void;
}

export function useContextHealthData(): UseContextHealthDataReturn {
  const [status, setStatus] = useState<ContextHealthStatus | null>(null);
  const [session, setSession] = useState<Record<string, unknown> | null>(null);
  const [kpis, setKpis] = useState<KpiResult[]>([]);
  const [charts, setCharts] = useState<ChartResult[]>([]);
  const [grids, setGrids] = useState<GridMeta[]>([]);
  const [activeGridId, setActiveGridId] = useState<string | null>(null);
  const [gridData, setGridData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusRes, sessionRes, kpisRes, chartsRes, gridsRes] = await Promise.all([
        fetchContextHealthStatus().catch(() => null),
        fetchContextHealthSession().catch(() => null),
        fetchContextHealthKpis().catch(() => []),
        fetchContextHealthCharts().catch(() => []),
        fetchContextHealthGrids().catch(() => []),
      ]);
      setStatus(statusRes);
      setSession(sessionRes);
      setKpis(kpisRes);
      setCharts(chartsRes);
      setGrids(gridsRes);
      if (gridsRes.length > 0 && !activeGridId) {
        setActiveGridId(gridsRes[0].gridId);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch context health data');
    } finally {
      setLoading(false);
    }
  }, [activeGridId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll, refreshKey]);

  useEffect(() => {
    if (!activeGridId) return;
    let cancelled = false;
    fetchContextHealthGridData(activeGridId)
      .then((data) => {
        if (!cancelled) setGridData(data);
      })
      .catch(() => {
        if (!cancelled) setGridData([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeGridId, refreshKey]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        setRefreshKey((k) => k + 1);
      }, 30_000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh]);

  const refresh = useCallback(() => {
    triggerRefresh().catch(() => {});
    setRefreshKey((k) => k + 1);
  }, []);

  const selectGrid = useCallback((gridId: string) => {
    setActiveGridId(gridId);
  }, []);

  const toggleAutoRefresh = useCallback(() => {
    setAutoRefresh((prev) => !prev);
  }, []);

  return {
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
  };
}
