import { api, type ApiInstance } from '@mfe/shared-http';
import { getShellServices } from '../../app/services/shell-services';
import type { KpiResult, ChartResult, GridMeta, ContextHealthStatus } from './types';

const BASE = '/v1/context-health';

const resolveHttpClient = (): ApiInstance => {
  try {
    return getShellServices().http;
  } catch {
    return api;
  }
};

export const fetchContextHealthStatus = async (): Promise<ContextHealthStatus> => {
  const client = resolveHttpClient();
  const { data } = await client.get<ContextHealthStatus>(`${BASE}/status`);
  return data;
};

export const fetchContextHealthKpis = async (): Promise<KpiResult[]> => {
  const client = resolveHttpClient();
  const { data } = await client.get<KpiResult[]>(`${BASE}/kpis`);
  return Array.isArray(data) ? data : [];
};

export const fetchContextHealthCharts = async (): Promise<ChartResult[]> => {
  const client = resolveHttpClient();
  const { data } = await client.get<ChartResult[]>(`${BASE}/charts`);
  return Array.isArray(data) ? data : [];
};

export const fetchContextHealthGrids = async (): Promise<GridMeta[]> => {
  const client = resolveHttpClient();
  const { data } = await client.get<GridMeta[]>(`${BASE}/grids`);
  return Array.isArray(data) ? data : [];
};

export const fetchContextHealthGridData = async (
  gridId: string,
): Promise<Record<string, unknown>[]> => {
  const client = resolveHttpClient();
  const { data } = await client.get<Record<string, unknown>[]>(`${BASE}/grids/${gridId}`);
  return Array.isArray(data) ? data : [];
};

export const fetchContextHealthSession = async (): Promise<Record<string, unknown>> => {
  const client = resolveHttpClient();
  const { data } = await client.get<Record<string, unknown>>(`${BASE}/session`);
  return data ?? {};
};

export const triggerRefresh = async (): Promise<void> => {
  const client = resolveHttpClient();
  await client.post(`${BASE}/refresh`);
};
