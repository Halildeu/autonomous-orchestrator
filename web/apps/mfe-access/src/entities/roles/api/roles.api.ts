import axios, { AxiosError } from 'axios';
import { api, type ApiInstance } from '@mfe/shared-http';
import type { AccessLevel, AccessModulePolicy, AccessRole } from '../../../features/access-management/model/access.types';
import { getShellServices } from '../../../app/services/shell-services';
import { mockAccessRoles } from '../../../features/access-management/lib/mock-data';

type RolePolicyDto = {
  moduleKey?: string;
  moduleLabel?: string;
  level?: string;
  lastUpdatedAt?: string;
  updatedBy?: string;
};

type RoleDto = {
  id?: string | number;
  name?: string;
  description?: string;
  memberCount?: number;
  systemRole?: boolean;
  lastModifiedAt?: string;
  lastModifiedBy?: string;
  policies?: RolePolicyDto[];
  permissions?: Array<string | number>;
};

type PagedResultDto<T> = {
  items?: T[];
  total?: number;
  page?: number;
  pageSize?: number;
};

type ErrorResponse = {
  error?: string;
  message?: string;
  fieldErrors?: Record<string, string[]>;
  meta?: { traceId?: string };
};

const parseError = (err: unknown) => {
  if (axios.isAxiosError(err)) {
    const res = err as AxiosError<ErrorResponse>;
    const data = res.response?.data;
    const msg = data?.message || data?.error || err.message || 'İstek başarısız';
    const traceId = data?.meta?.traceId;
    if (traceId) {
      console.warn(`[roles.api] traceId=${traceId} message=${msg}`, data?.fieldErrors);
    }
    throw new Error(msg);
  }
  throw err;
};

const resolveHttpClient = (): ApiInstance => {
  try {
    return getShellServices().http;
  } catch {
    return api;
  }
};

const isDevelopmentFallbackEnabled = () => process.env.NODE_ENV !== 'production';

const toAccessLevel = (value?: string): AccessLevel => {
  const upper = (value || '').toUpperCase();
  if (upper === 'VIEW') return 'VIEW';
  if (upper === 'EDIT') return 'MANAGE'; // EDIT → MANAGE per STORY-0318 K1
  if (upper === 'MANAGE') return 'MANAGE';
  return 'NONE';
};

const mapPolicy = (dto: RolePolicyDto): AccessModulePolicy => ({
  moduleKey: dto.moduleKey ?? dto.moduleLabel ?? 'UNKNOWN',
  moduleLabel: dto.moduleLabel ?? dto.moduleKey ?? 'Bilinmeyen Modül',
  level: toAccessLevel(dto.level),
  lastUpdatedAt: dto.lastUpdatedAt ?? '',
  updatedBy: dto.updatedBy ?? 'system',
});

const mapRole = (dto: RoleDto): AccessRole => ({
  id: String(dto.id ?? ''),
  name: dto.name ?? 'Bilinmeyen Rol',
  description: dto.description,
  memberCount: typeof dto.memberCount === 'number' ? dto.memberCount : 0,
  isSystemRole: dto.systemRole ?? false,
  policies: Array.isArray(dto.policies) ? dto.policies.map(mapPolicy) : [],
  lastModifiedAt: dto.lastModifiedAt ?? '',
  lastModifiedBy: dto.lastModifiedBy ?? 'system',
  permissions: Array.isArray(dto.permissions) ? dto.permissions.map((p) => String(p)) : [],
});

export const getRoles = async (): Promise<{ items: AccessRole[]; total: number }> => {
  try {
    const client = resolveHttpClient();
    const res = await client.get<PagedResultDto<RoleDto>>('/v1/roles');
    const items = Array.isArray(res.data.items) ? res.data.items.map(mapRole) : [];
    const total = typeof res.data.total === 'number' ? res.data.total : items.length;
    return { items, total };
  } catch (err: unknown) {
    if (isDevelopmentFallbackEnabled()) {
      return { items: mockAccessRoles, total: mockAccessRoles.length };
    }
    parseError(err);
  }
};

export const getRole = async (id: string): Promise<AccessRole> => {
  try {
    const client = resolveHttpClient();
    const res = await client.get<RoleDto>(`/v1/roles/${encodeURIComponent(id)}`);
    return mapRole(res.data);
  } catch (err: unknown) {
    if (isDevelopmentFallbackEnabled()) {
      const fallback = mockAccessRoles.find((role) => role.id === id);
      if (fallback) {
        return fallback;
      }
    }
    parseError(err);
  }
};

export type CreateRoleRequestDto = {
  name: string;
  description?: string;
};

export const createRole = async (payload: CreateRoleRequestDto): Promise<AccessRole> => {
  try {
    const client = resolveHttpClient();
    const res = await client.post<RoleDto>('/v1/roles', payload);
    return mapRole(res.data);
  } catch (err: unknown) {
    parseError(err);
  }
};

export type UpdateRoleRequestDto = {
  name?: string;
  description?: string;
};

export const updateRole = async (id: string, payload: UpdateRoleRequestDto): Promise<AccessRole> => {
  try {
    const client = resolveHttpClient();
    const res = await client.put<RoleDto>(`/v1/roles/${encodeURIComponent(id)}`, payload);
    return mapRole(res.data);
  } catch (err: unknown) {
    parseError(err);
  }
};

export type CloneRoleRequestDto = {
  name: string;
  description?: string;
  copyMemberCount?: boolean;
};

export type CloneRoleResponseDto = {
  role?: RoleDto;
  auditId?: string;
};

export const cloneRole = async (
  id: string,
  payload: CloneRoleRequestDto,
): Promise<{ role: AccessRole; auditId?: string }> => {
  try {
    const client = resolveHttpClient();
    const res = await client.post<CloneRoleResponseDto>(`/v1/roles/${encodeURIComponent(id)}/clone`, payload);
    return {
      role: mapRole(res.data.role ?? {}),
      auditId: res.data.auditId,
    };
  } catch (err: unknown) {
    parseError(err);
  }
};

export type UpdateRolePermissionsRequestDto = {
  permissionIds: string[];
};

export const deleteRole = async (id: string): Promise<void> => {
  try {
    const client = resolveHttpClient();
    await client.delete(`/v1/roles/${encodeURIComponent(id)}`);
  } catch (err: unknown) {
    parseError(err);
  }
};

export const updateRolePermissions = async (
  id: string,
  payload: UpdateRolePermissionsRequestDto,
): Promise<{ updated: boolean; auditId?: string }> => {
  try {
    const client = resolveHttpClient();
    const res = await client.put<{ auditId?: string }>(`/v1/roles/${encodeURIComponent(id)}/permissions`, payload);
    return { updated: true, auditId: res.data.auditId };
  } catch (err: unknown) {
    parseError(err);
  }
};
