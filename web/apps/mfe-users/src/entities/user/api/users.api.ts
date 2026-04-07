import { AxiosError, isAxiosError } from 'axios';
import { api, getGatewayBaseUrl } from '@mfe/shared-http';
import type { ApiInstance } from '@mfe/shared-http';
import { PaginatedResponse, UserDetail, UserSummary } from '@mfe/shared-types';
import type { UserModuleAccessLevel, UserModulePermission } from '@mfe/shared-types';
import { UsersQueryParams } from '../../../features/user-management/model/user-management.types';
import {
  registerTokenResolver as registerSharedTokenResolver,
} from '../lib/token-resolver.lib';
import { getShellServices } from '../../../app/services/shell-services';

const API_BASE_URL = getGatewayBaseUrl();
const USERS_RESOURCE_PATH = '/v1/users';
const AUTH_RESOURCE_PATH = '/v1/auth';
const PERMISSIONS_RESOURCE_PATH = '/v1/permissions';
const UNAUTHORIZED_STATUS = new Set([401, 403]);
const PROFILE_MISSING_CODE = 'PROFILE_MISSING';

const getFetchBaseUrl = () => {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return 'http://localhost';
};

const buildGatewayUrl = (resourcePath: string) => `${API_BASE_URL}${resourcePath}`;

const buildFetchGatewayUrl = (resourcePath: string) => `${getFetchBaseUrl()}${buildGatewayUrl(resourcePath)}`;

const resolveHttpClient = (): ApiInstance => {
  try {
    return getShellServices().http;
  } catch {
    return api;
  }
};

type ErrorResponseWire = {
  error?: unknown;
  message?: unknown;
  fieldErrors?: Record<string, string[]>;
  meta?: { traceId?: string };
};

type ParsedError = {
  message: string;
  fieldErrors?: Record<string, string[]>;
  traceId?: string;
};

export type UserMutationAck = {
  status?: string;
  auditId?: string;
};

/**
 * @deprecated STORY-0318: Module lists now come from /v1/authz/catalog.
 * These hardcoded lists are kept temporarily for backward compatibility.
 */
const KNOWN_MODULES: Array<{ key: string; label: string }> = [
  { key: 'USER_MANAGEMENT', label: 'Kullanıcı Modülü' },
  { key: 'PURCHASE', label: 'Satın Alma Modülü' },
  { key: 'WAREHOUSE', label: 'Depo Modülü' },
];

/**
 * @deprecated STORY-0318: Role assignment now uses POST /v1/authz/users/{id}/assignments.
 * This mapping is kept temporarily for backward compatibility.
 */
const MODULE_LEVEL_ROLE_MAP: Record<string, Partial<Record<UserModuleAccessLevel, string>>> = {
  USER_MANAGEMENT: {
    VIEW: 'USER_VIEWER',
    MANAGE: 'USER_MANAGER',
  },
  PURCHASE: {
    VIEW: 'PURCHASE_MANAGER',
    MANAGE: 'PURCHASE_MANAGER',
  },
  WAREHOUSE: {
    VIEW: 'WAREHOUSE_OPERATOR',
    MANAGE: 'WAREHOUSE_OPERATOR',
  },
};

export interface UsersApiResponse extends PaginatedResponse<UserSummary> {
  meta?: {
    reason: 'success' | 'unauthorized' | 'profile-missing' | 'network-error';
  };
}

type UsersResponseWire = {
  items?: unknown;
  total?: unknown;
  page?: unknown;
  pageSize?: unknown;
};

type UserSummaryWire = {
  id?: unknown;
  email?: unknown;
  fullName?: unknown;
  name?: unknown;
  modulePermissions?: unknown;
  enabled?: unknown;
  role?: unknown;
  lastLogin?: unknown;
  lastLoginAt?: unknown;
  createDate?: unknown;
  createdAt?: unknown;
  sessionTimeoutMinutes?: unknown;
};

type PermissionWire = Partial<UserModulePermission> & {
  key?: unknown;
  module?: unknown;
  label?: unknown;
  moduleName?: unknown;
  permissionModules?: Record<string, string>;
};

type AssignmentWire = PermissionWire & { active?: boolean };

type UserDetailWire = UserSummaryWire & {
  phoneNumber?: unknown;
  title?: unknown;
  locale?: unknown;
  timezone?: unknown;
  notes?: unknown;
  status?: unknown;
  firstName?: unknown;
  lastName?: unknown;
};

const isPermissionWire = (value: unknown): value is PermissionWire =>
  typeof value === 'object' && value !== null;

const toStringOrFallback = (value: unknown, fallback = ''): string => {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return fallback;
};

const buildEmptyUsersResponse = (params: UsersQueryParams = {}): PaginatedResponse<UserSummary> => ({
  items: [],
  total: 0,
  page: params.page ?? 1,
  pageSize: params.pageSize ?? 25,
});

const readRuntimeEnv = (key: string): string | undefined => {
  if (typeof process !== 'undefined' && typeof process.env?.[key] === 'string') {
    return process.env[key];
  }
  if (typeof window !== 'undefined') {
    const runtimeWindow = window as Window & {
      __env__?: Record<string, string | undefined>;
      __ENV__?: Record<string, string | undefined>;
    };
    const candidate = runtimeWindow.__env__?.[key] ?? runtimeWindow.__ENV__?.[key];
    if (typeof candidate === 'string') {
      return candidate;
    }
  }
  return undefined;
};

const parseRuntimeBoolean = (value: string | undefined): boolean => {
  if (!value) {
    return false;
  }
  const normalized = value.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
};

const normalizeTokenValue = (token: string | null | undefined): string => {
  if (typeof token !== 'string') {
    return '';
  }
  const normalized = token.trim();
  if (!normalized || normalized === 'undefined' || normalized === 'null') {
    return '';
  }
  return normalized;
};

const readPersistedToken = (): string => {
  try {
    return normalizeTokenValue(localStorage.getItem('token'));
  } catch {
    return '';
  }
};

type LightweightUserProfile = {
  email?: string | null;
  fullName?: string | null;
  displayName?: string | null;
  role?: string | null;
};

const readPersistedUserProfile = (): LightweightUserProfile | null => {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') {
      return null;
    }
    return parsed as LightweightUserProfile;
  } catch {
    return null;
  }
};

const readShellAuthToken = (): string => {
  try {
    return normalizeTokenValue(getShellServices().auth.getToken());
  } catch {
    return '';
  }
};

const readShellAuthUser = (): LightweightUserProfile | null => {
  try {
    const user = getShellServices().auth.getUser();
    if (!user || typeof user !== 'object') {
      return null;
    }
    return user as LightweightUserProfile;
  } catch {
    return null;
  }
};

const isRuntimeTestProfile = (profile: LightweightUserProfile | null): boolean => {
  if (!profile) {
    return false;
  }
  const email = profile.email?.trim().toLowerCase() ?? '';
  const fullName = profile.fullName?.trim().toLowerCase() ?? '';
  const displayName = profile.displayName?.trim().toLowerCase() ?? '';

  return email === 'runtime@test.local'
    || fullName === 'runtime test user'
    || displayName === 'runtime test user';
};

const shouldUseDevUsersFallback = (): boolean => {
  const devFallbackDisabled = parseRuntimeBoolean(
    readRuntimeEnv('VITE_USERS_DISABLE_DEV_FALLBACK') ?? readRuntimeEnv('USERS_DISABLE_DEV_FALLBACK'),
  );
  const authMode = (readRuntimeEnv('VITE_AUTH_MODE') ?? readRuntimeEnv('AUTH_MODE') ?? '').trim().toLowerCase();
  const fakeAuthEnabled = parseRuntimeBoolean(
    readRuntimeEnv('VITE_ENABLE_FAKE_AUTH') ?? readRuntimeEnv('ENABLE_FAKE_AUTH'),
  );
  const token = readPersistedToken().trim() || readShellAuthToken();
  const runtimeUser = readPersistedUserProfile() ?? readShellAuthUser();

  if (devFallbackDisabled) {
    return false;
  }

  if (authMode === 'permitall') {
    return true;
  }

  // Fake shell oturumu ".shell" ile biten sentetik JWT üretir.
  // Bu durumda runtime env görünmese bile backend'e gitmek yerine
  // doğrudan güvenli mock kullanıcı verisini kullanıyoruz.
  if (token.endsWith('.shell')) {
    return true;
  }

  if (fakeAuthEnabled) {
    return true;
  }

  return isRuntimeTestProfile(runtimeUser);
};

const MOCK_USER_DETAILS: UserDetail[] = [
  {
    id: 'mock-user-001',
    fullName: 'Selin Aydin',
    email: 'selin.aydin@example.com',
    role: 'ADMIN',
    status: 'ACTIVE',
    lastLoginAt: '2026-03-14T08:45:00Z',
    createdAt: '2025-10-03T09:00:00Z',
    sessionTimeoutMinutes: 30,
    locale: 'tr-TR',
    timezone: 'Europe/Istanbul',
    title: 'Platform Yoneticisi',
    phoneNumber: '+90 555 010 1001',
    notes: 'PermitAll gelistirme modunda ornek yonetici kullanici.',
    modulePermissions: [
      {
        moduleKey: 'USER_MANAGEMENT',
        moduleLabel: 'Kullanici Modulu',
        level: 'MANAGE',
        roleName: 'ADMIN',
        permissions: ['VIEW_USERS', 'EDIT_USERS', 'MANAGE_USERS'],
      },
      {
        moduleKey: 'PURCHASE',
        moduleLabel: 'Satin Alma Modulu',
        level: 'VIEW',
        roleName: 'PURCHASE_MANAGER',
        permissions: ['VIEW_PURCHASE'],
      },
    ],
  },
  {
    id: 'mock-user-002',
    fullName: 'Emir Kara',
    email: 'emir.kara@example.com',
    role: 'USER',
    status: 'ACTIVE',
    lastLoginAt: '2026-03-13T16:20:00Z',
    createdAt: '2025-12-11T10:15:00Z',
    sessionTimeoutMinutes: 20,
    locale: 'tr-TR',
    timezone: 'Europe/Istanbul',
    title: 'Kullanici Operasyon Uzmani',
    phoneNumber: '+90 555 010 1002',
    notes: 'Kullanicilari goruntuleyebilir ve sinirli duzenleme yapabilir.',
    modulePermissions: [
      {
        moduleKey: 'USER_MANAGEMENT',
        moduleLabel: 'Kullanici Modulu',
        level: 'EDIT',
        roleName: 'USER_MANAGER',
        permissions: ['VIEW_USERS', 'EDIT_USERS'],
      },
      {
        moduleKey: 'WAREHOUSE',
        moduleLabel: 'Depo Modulu',
        level: 'VIEW',
        roleName: 'WAREHOUSE_OPERATOR',
        permissions: ['VIEW_WAREHOUSE'],
      },
    ],
  },
  {
    id: 'mock-user-003',
    fullName: 'Derya Demir',
    email: 'derya.demir@example.com',
    role: 'USER',
    status: 'INVITED',
    lastLoginAt: null,
    createdAt: '2026-01-20T14:10:00Z',
    sessionTimeoutMinutes: 15,
    locale: 'en-US',
    timezone: 'Europe/Berlin',
    title: 'Destek Uzmani',
    phoneNumber: '+90 555 010 1003',
    notes: 'Davet gonderilmis, ilk oturumunu henuz acmamis kullanici.',
    modulePermissions: [
      {
        moduleKey: 'USER_MANAGEMENT',
        moduleLabel: 'Kullanici Modulu',
        level: 'VIEW',
        roleName: 'USER_VIEWER',
        permissions: ['VIEW_USERS'],
      },
    ],
  },
];

const sortMockUsers = (items: UserDetail[], sort?: string): UserDetail[] => {
  if (!sort) {
    return [...items];
  }

  const [firstSort] = sort.split(';').map((segment) => segment.trim()).filter(Boolean);
  if (!firstSort) {
    return [...items];
  }

  const [fieldRaw, directionRaw] = firstSort.split(',');
  const field = (fieldRaw ?? '').trim();
  const direction = (directionRaw ?? 'asc').trim().toLowerCase() === 'desc' ? -1 : 1;

  const readValue = (item: UserDetail) => {
    switch (field) {
      case 'name':
      case 'fullName':
        return item.fullName;
      case 'email':
        return item.email;
      case 'role':
        return item.role;
      case 'status':
        return item.status;
      case 'lastLogin':
      case 'lastLoginAt':
        return item.lastLoginAt ?? '';
      case 'sessionTimeoutMinutes':
        return item.sessionTimeoutMinutes ?? 0;
      default:
        return item.fullName;
    }
  };

  return [...items].sort((left, right) => {
    const leftValue = readValue(left);
    const rightValue = readValue(right);
    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * direction;
    }
    return String(leftValue).localeCompare(String(rightValue), 'tr') * direction;
  });
};

const buildMockUsersResponse = (params: UsersQueryParams = {}): UsersApiResponse => {
  const search = params.search?.trim().toLocaleLowerCase('tr') ?? '';
  const filtered = sortMockUsers(
    MOCK_USER_DETAILS.filter((item) => {
      const matchesSearch =
        search.length === 0 ||
        item.fullName.toLocaleLowerCase('tr').includes(search) ||
        item.email.toLocaleLowerCase('tr').includes(search);
      const matchesStatus = !params.status || params.status === 'ALL' || item.status === params.status;
      const matchesRole = !params.role || params.role === 'ALL' || item.role === params.role;
      const matchesModuleKey =
        !params.moduleKey ||
        item.modulePermissions.some((permission) => permission.moduleKey === params.moduleKey);
      const matchesModuleLevel =
        !params.moduleLevel ||
        params.moduleLevel === 'ALL' ||
        item.modulePermissions.some((permission) => permission.level === params.moduleLevel);

      return matchesSearch && matchesStatus && matchesRole && matchesModuleKey && matchesModuleLevel;
    }),
    params.sort,
  );

  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? 25;

  if (pageSize === 0) {
    return {
      items: filtered,
      total: filtered.length,
      page,
      pageSize: filtered.length,
      meta: { reason: 'success' },
    };
  }

  const start = Math.max(0, (page - 1) * pageSize);
  const end = start + pageSize;

  return {
    items: filtered.slice(start, end),
    total: filtered.length,
    page,
    pageSize,
    meta: { reason: 'success' },
  };
};

const buildMockUserDetail = (user: { id: string; email: string }): UserDetail => {
  const matched = MOCK_USER_DETAILS.find((item) => item.id === user.id || item.email === user.email);
  if (matched) {
    return matched;
  }
  return buildFallbackUserDetail(user);
};

const shouldUseFetchTransportStub = (): boolean => typeof fetch === 'function' && typeof document === 'undefined';

const isProfileMissingPayload = (payload: unknown): boolean => {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const record = payload as Record<string, unknown>;
  return [record.message, record.error, record.errorCode, record.detail].some(
    (value) => typeof value === 'string' && value.trim().toUpperCase() === PROFILE_MISSING_CODE,
  );
};

const detectProfileMissingFromResponse = async (response: { clone?: () => Response; json?: () => Promise<unknown> }) => {
  try {
    if (typeof response.clone === 'function') {
      return isProfileMissingPayload(await response.clone().json());
    }
    if (typeof response.json === 'function') {
      return isProfileMissingPayload(await response.json());
    }
  } catch {
    // ignore payload parsing errors
  }
  return false;
};

const buildFallbackUserDetail = (
  user: { id: string; email: string },
): UserDetail => ({
  id: user.id,
  email: user.email,
  fullName: user.email,
  role: 'USER',
  status: 'ACTIVE',
  lastLoginAt: null,
  createdAt: null,
  modulePermissions: ensureAdminUserModulePermission([], null),
  phoneNumber: undefined,
  title: undefined,
  locale: undefined,
  timezone: undefined,
  notes: undefined,
  sessionTimeoutMinutes: 15,
});

export interface RequestScope {
  companyId?: string | number;
  projectId?: string | number;
  warehouseId?: string | number;
}

type ControlledAccessRequestConfig = {
  headers: Record<string, string>;
  __suppressGlobalForbiddenToast: true;
  __suppressGlobalProfileMissingToast: true;
};

const SCOPE_STORAGE_KEY = 'halo.scope';

export const registerTokenResolver = (resolver?: Parameters<typeof registerSharedTokenResolver>[0]) => {
  registerSharedTokenResolver(resolver);
};

const getStoredScope = (): RequestScope => {
  try {
    const raw = localStorage.getItem(SCOPE_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) {
      return {};
    }
    return parsed as RequestScope;
  } catch (error: unknown) {
    console.warn('Scope bilgisi çözümlenemedi', error);
    return {};
  }
};

const buildScopeHeaders = (scope?: RequestScope) => {
  const ctx = scope ?? getStoredScope();
  const headers: Record<string, string> = {};
  if (ctx.companyId !== undefined && ctx.companyId !== null) {
    headers['X-Company-Id'] = String(ctx.companyId);
  }
  if (ctx.projectId !== undefined && ctx.projectId !== null) {
    headers['X-Project-Id'] = String(ctx.projectId);
  }
  if (ctx.warehouseId !== undefined && ctx.warehouseId !== null) {
    headers['X-Warehouse-Id'] = String(ctx.warehouseId);
  }
  return headers;
};

const parseErrorResponse = async (
  source: Response | AxiosError<ErrorResponseWire> | undefined,
): Promise<ParsedError> => {
  if (source && typeof Response !== 'undefined' && source instanceof Response) {
    try {
      const payload = (await source.json()) as ErrorResponseWire;
      const message =
        typeof payload.message === 'string'
          ? payload.message
          : typeof payload.error === 'string'
            ? payload.error
            : `İstek başarısız (${source.status})`;
      return {
        message,
        fieldErrors: payload.fieldErrors,
        traceId: payload.meta?.traceId,
      };
    } catch {
      return { message: `İstek başarısız (${source.status})` };
    }
  }

  if (source && isAxiosError<ErrorResponseWire>(source)) {
    const payload = source.response?.data;
    const message =
      (payload?.message as string) ??
      (payload?.error as string) ??
      `İstek başarısız (${source.response?.status ?? '??'})`;
    return {
      message,
      fieldErrors: payload?.fieldErrors,
      traceId: payload?.meta?.traceId,
    };
  }

  return { message: 'İstek başarısız oldu.' };
};

const reportError = (context: string, parsed: ParsedError) => {
  const traceInfo = parsed.traceId ? ` traceId=${parsed.traceId}` : '';
  console.warn(`[usersApi] ${context} hata: ${parsed.message}${traceInfo}`, parsed.fieldErrors);
};

const buildQueryString = (params: UsersQueryParams) => {
  const qs = new URLSearchParams();
  if (params.search) qs.set('search', params.search);
  if (params.advancedFilter) qs.set('advancedFilter', params.advancedFilter);
  if (params.sort) qs.set('sort', params.sort);
  if (params.status && params.status !== 'ALL') qs.set('status', params.status);
  if (params.role && params.role !== 'ALL') qs.set('role', params.role);
  if (params.page) qs.set('page', params.page.toString());
  if (params.pageSize != null) qs.set('pageSize', params.pageSize.toString());
  // Server-side grouping params
  if ((params as any).rowGroupCols) qs.set('rowGroupCols', (params as any).rowGroupCols);
  if ((params as any).groupKeys) qs.set('groupKeys', (params as any).groupKeys);
  // Server-side aggregation + pivot params
  if ((params as any).valueCols) qs.set('valueCols', (params as any).valueCols);
  if ((params as any).pivotMode) qs.set('pivotMode', (params as any).pivotMode);
  if ((params as any).pivotCols) qs.set('pivotCols', (params as any).pivotCols);
  // Multi-value search (from filter builder bulk paste)
  if ((params as any).multiSearch) qs.set('multiSearch', (params as any).multiSearch);
  const queryString = qs.toString();
  return queryString ? `?${queryString}` : '';
};

const mergeHeaders = (scope?: RequestScope) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...buildScopeHeaders(scope),
  };
  try {
    const shellToken = readShellAuthToken().trim();
    if (typeof window !== 'undefined' && window.localStorage) {
      const internalApiKey = window.localStorage.getItem('internalApiKey');
      if (internalApiKey) {
        headers['X-Internal-Api-Key'] = internalApiKey;
      }
      const persistedToken = normalizeTokenValue(window.localStorage.getItem('token'));
      const token = shellToken || persistedToken;
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch (error: unknown) {
    console.warn('Internal API anahtarı okunamadı', error);
  }
  return headers;
};

const buildControlledAccessRequestConfig = (scope?: RequestScope): ControlledAccessRequestConfig => ({
  headers: mergeHeaders(scope),
  __suppressGlobalForbiddenToast: true,
  __suppressGlobalProfileMissingToast: true,
});

const normalizeAccessLevel = (value: unknown): UserModuleAccessLevel => {
  if (typeof value === 'string') {
    const normalized = value.toUpperCase();
    if (normalized === 'OWNER' || normalized === 'MANAGE') {
      return 'MANAGE';
    }
    if (normalized === 'EDITOR' || normalized === 'EDIT') {
      return 'EDIT';
    }
    if (normalized === 'VIEW') {
      return 'VIEW';
    }
  }
  return 'NONE';
};

const normalizeUsersResponse = (
  payload: UsersResponseWire,
  params: UsersQueryParams,
): UsersApiResponse => {
  const items = Array.isArray(payload.items)
    ? payload.items.map((userItem) => {
        const user = userItem as UserSummaryWire;
        const role = typeof user.role === 'string' ? user.role : 'USER';
        const rawModulePermissions = Array.isArray(user.modulePermissions)
          ? user.modulePermissions
          : [];

        const normalizedModulePermissions: UserModulePermission[] = rawModulePermissions
          .filter(isPermissionWire)
          .map((permission) => {
            const moduleKey = toStringOrFallback(
              permission.moduleKey ?? permission.key ?? permission.module ?? '',
            );
            const rawPermissions = Array.isArray(permission.permissions)
              ? permission.permissions.map((code) => toStringOrFallback(code, '').toUpperCase())
              : [];
            let level = normalizeAccessLevel(permission.level);

            if (level === 'NONE') {
              if (rawPermissions.includes('MANAGE_USERS')) {
                level = 'MANAGE';
              } else if (rawPermissions.includes('EDIT_USERS')) {
                level = 'EDIT';
              } else if (rawPermissions.includes('VIEW_USERS')) {
                level = 'VIEW';
              } else if (typeof permission.roleName === 'string') {
                const normalizedRole = permission.roleName.toUpperCase();
                if (['USER_MANAGER', 'ADMIN', 'OWNER'].includes(normalizedRole)) {
                  level = 'MANAGE';
                } else if (['USER_EDITOR', 'EDITOR'].includes(normalizedRole)) {
                  level = 'EDIT';
                } else if (['USER_VIEWER', 'VIEWER'].includes(normalizedRole)) {
                  level = 'VIEW';
                }
              }
            }

            return {
              moduleKey,
              moduleLabel: toStringOrFallback(permission.moduleLabel, moduleKey),
              permissions: rawPermissions,
              level,
              roleName: toStringOrFallback(permission.roleName, role),
              companyId: permission.companyId ?? null,
            };
          });

        return {
          id: user.id ?? '',
          email: toStringOrFallback(user.email, ''),
          fullName: toStringOrFallback(user.fullName ?? user.name, user.email ?? ''),
          role,
          status: typeof user.status === 'string' ? user.status.toUpperCase() : 'ACTIVE',
          modulePermissions: normalizedModulePermissions,
          companyId: user.companyId ?? null,
        };
      })
    : [];

  return {
    items,
    total: typeof payload.total === 'number' ? payload.total : items.length,
    page: typeof payload.page === 'number' ? payload.page : params.page ?? 1,
    pageSize: typeof payload.pageSize === 'number' ? payload.pageSize : params.pageSize ?? items.length,
    meta: { reason: 'success' },
  };
};

const normalizeUserDetail = (
  userData: UserDetailWire,
  assignments: AssignmentWire[],
  user: { id: string; email: string },
): UserDetail => {
  const deriveName = () => {
    if (typeof userData.fullName === 'string' && userData.fullName.trim().length > 0) {
      return userData.fullName;
    }
    if (typeof userData.name === 'string' && userData.name.trim().length > 0) {
      return userData.name;
    }
    const firstName = typeof userData.firstName === 'string' ? userData.firstName : '';
    const lastName = typeof userData.lastName === 'string' ? userData.lastName : '';
    if (firstName || lastName) {
      return `${firstName} ${lastName}`.trim();
    }
    return user.email;
  };

  const status = userData.status
    ? String(userData.status).toUpperCase()
    : userData.enabled === false
      ? 'INACTIVE'
      : 'ACTIVE';

  const activeAssignments = assignments.filter((assignment) => assignment?.active !== false);

  const assignmentMap = new Map<string, UserModulePermission & { moduleMetadata?: Record<string, string> }>();

  activeAssignments.forEach((assignment) => {
    const moduleKeyRaw = toStringOrFallback(assignment.moduleKey ?? assignment.key ?? assignment.module, '').trim();
    const moduleKey = moduleKeyRaw ? moduleKeyRaw.toUpperCase() : undefined;

    const permissions: string[] = Array.isArray(assignment.permissions)
      ? assignment.permissions
          .filter((code: unknown) => typeof code === 'string' && code.length > 0)
          .map((code: string) => code.toUpperCase())
      : [];

    const permissionLevel = deriveModuleLevelFromPermissions(moduleKey, permissions, assignment.roleName);

    if (!moduleKey) {
      return;
    }

    const moduleLabel = assignment.moduleLabel ?? assignment.label ?? assignment.moduleName ?? moduleKey;

    assignmentMap.set(moduleKey, {
      moduleKey,
      moduleLabel,
      level: permissionLevel,
      assignmentId: assignment.assignmentId ? String(assignment.assignmentId) : undefined,
      roleName: assignment.roleName,
      permissions,
      companyId: assignment.companyId ? String(assignment.companyId) : undefined,
      moduleMetadata: assignment.permissionModules ?? undefined,
    });
  });

  KNOWN_MODULES.forEach((module) => {
    if (!assignmentMap.has(module.key)) {
      assignmentMap.set(module.key, {
        moduleKey: module.key,
        moduleLabel: module.label,
        level: 'NONE',
        assignmentId: undefined,
        roleName: undefined,
        permissions: [],
        companyId: undefined,
      });
    }
  });

  const modulePermissions = Array.from(assignmentMap.values()).sort((a, b) => {
    const aIndex = KNOWN_MODULES.findIndex((item) => item.key === a.moduleKey);
    const bIndex = KNOWN_MODULES.findIndex((item) => item.key === b.moduleKey);
    if (aIndex !== -1 && bIndex !== -1) {
      return aIndex - bIndex;
    }
    if (aIndex !== -1) {
      return -1;
    }
    if (bIndex !== -1) {
      return 1;
    }
    return a.moduleKey.localeCompare(b.moduleKey);
  });

  return {
    id: String(user.id ?? ''),
    fullName: deriveName(),
    email: toStringOrFallback(userData.email ?? user.email, ''),
    role: typeof userData.role === 'string' ? userData.role.toUpperCase() : 'USER',
    status,
    lastLoginAt: (userData.lastLogin ?? userData.lastLoginAt ?? null) as string | null,
    createdAt: (userData.createDate ?? userData.createdAt ?? null) as string | null,
    sessionTimeoutMinutes:
      typeof userData.sessionTimeoutMinutes === 'number'
        ? userData.sessionTimeoutMinutes
        : 15,
    modulePermissions: ensureAdminUserModulePermission(modulePermissions, userData.role),
  };
};

const ensureAdminUserModulePermission = (
  modulePermissions: UserModulePermission[],
  role?: string | null,
): UserModulePermission[] => {
  if (!role || role.toUpperCase() !== 'ADMIN') {
    return modulePermissions;
  }

  const permissions = [...modulePermissions];
  const targetKey = 'USER_MANAGEMENT';

  const existingIndex = permissions.findIndex(
    (permission) => permission.moduleKey === targetKey,
  );

  if (existingIndex >= 0) {
    const existing = permissions[existingIndex];
    permissions[existingIndex] = {
      ...existing,
      moduleLabel: existing.moduleLabel ?? 'Kullanıcı Modülü',
    };
  } else {
    permissions.push({
      moduleKey: targetKey,
      moduleLabel: 'Kullanıcı Modülü',
      level: 'MANAGE',
      permissions: ['VIEW_USERS', 'EDIT_USERS', 'MANAGE_USERS'],
    });
  }

  return permissions;
};

const deriveModuleLevelFromPermissions = (
  moduleKey: string | undefined,
  permissions: string[],
  roleName?: string,
): UserModuleAccessLevel => {
  const normalizedPermissions = permissions.map((code) => code.toUpperCase());
  const normalizedRole = roleName?.toUpperCase();

  if (moduleKey && normalizedRole) {
    const roles = MODULE_LEVEL_ROLE_MAP[moduleKey];
    if (roles) {
      const levelPriority: UserModuleAccessLevel[] = ['MANAGE', 'EDIT', 'VIEW'];
      for (const level of levelPriority) {
        const mappedRole = roles[level];
        if (mappedRole && normalizedRole === mappedRole.toUpperCase()) {
          return level;
        }
      }
    }
  }

  if (normalizedPermissions.some((code) => code.startsWith('MANAGE_') || code.startsWith('APPROVE_'))) {
    return 'MANAGE';
  }
  if (normalizedPermissions.some((code) => code.startsWith('EDIT_'))) {
    return 'EDIT';
  }
  if (normalizedPermissions.some((code) => code.startsWith('VIEW_'))) {
    return 'VIEW';
  }

  if (normalizedRole) {
    if (normalizedRole.includes('MANAGER') || normalizedRole.includes('OPERATOR') || normalizedRole.includes('ADMIN')) {
      return 'MANAGE';
    }
    if (normalizedRole.includes('EDITOR')) {
      return 'EDIT';
    }
    if (normalizedRole.includes('VIEW')) {
      return 'VIEW';
    }
  }

  return 'NONE';
};

export const fetchUsers = async (
  params: UsersQueryParams,
  scope?: RequestScope,
): Promise<UsersApiResponse> => {
  if (shouldUseDevUsersFallback()) {
    return buildMockUsersResponse(params);
  }

  let payload: UsersResponseWire;

  // Eğer global fetch stub'ı varsa (test ortamları), axios yerine doğrudan fetch kullan
  if (shouldUseFetchTransportStub()) {
    const headers = mergeHeaders(scope) as Record<string, string>;
    try {
      const response = await fetch(`${buildFetchGatewayUrl(USERS_RESOURCE_PATH)}${buildQueryString(params)}`, {
        headers,
      });
      if (!response.ok) {
        if (UNAUTHORIZED_STATUS.has(response.status)) {
          const reason =
            response.status === 403 && (await detectProfileMissingFromResponse(response))
              ? ('profile-missing' as const)
              : ('unauthorized' as const);
          return Object.assign(buildEmptyUsersResponse(params), {
            meta: { reason },
          });
        }
        return Object.assign(buildEmptyUsersResponse(params), {
          meta: { reason: 'network-error' as const },
        });
      }
      payload = ((await response.json()) ?? {}) as UsersResponseWire;
    } catch {
      return Object.assign(buildEmptyUsersResponse(params), {
        meta: { reason: 'network-error' as const },
      });
    }
    return normalizeUsersResponse(payload, params);
  }

  try {
    const client = resolveHttpClient();
    const response = await client.get<UsersResponseWire>(
      `${USERS_RESOURCE_PATH}${buildQueryString(params)}`,
      buildControlledAccessRequestConfig(scope),
    );
    payload = response.data ?? {};
  } catch (error: unknown) {
    if (isAxiosError(error)) {
      const status = error.response?.status ?? 0;
      if (!error.response) {
        console.warn('[usersApi] Kullanıcı listesi alınamadı, bağlantı hatası.', error);
        return Object.assign(buildEmptyUsersResponse(params), {
          meta: { reason: 'network-error' as const },
        });
      }
      if (UNAUTHORIZED_STATUS.has(status)) {
        const reason =
          status === 403 && isProfileMissingPayload(error.response?.data)
            ? ('profile-missing' as const)
            : ('unauthorized' as const);
        console.warn(
          '[usersApi] Kullanıcı listesi yetkisiz döndü. Boş sonuç ile devam ediliyor.',
        );
        return Object.assign(buildEmptyUsersResponse(params), {
          meta: { reason },
        });
      }
      const parsed = await parseErrorResponse(error);
      reportError('Kullanıcı listesi', parsed);
      throw new Error(parsed.message);
    }
    throw error;
  }

  const items = Array.isArray(payload.items)
    ? payload.items.map((userItem) => {
        const user = userItem as UserSummaryWire;
        const role = typeof user.role === 'string' ? user.role : 'USER';
        const rawModulePermissions = Array.isArray(user.modulePermissions)
          ? user.modulePermissions
          : [];

        const normalizedModulePermissions: UserModulePermission[] = rawModulePermissions
          .filter(isPermissionWire)
          .map((permission) => {
            const moduleKey = toStringOrFallback(
              permission.moduleKey ?? permission.key ?? permission.module ?? '',
            );
            const rawPermissions = Array.isArray(permission.permissions)
              ? permission.permissions.map((code) => toStringOrFallback(code, '').toUpperCase())
              : [];
            let level = normalizeAccessLevel(permission.level);

            if (level === 'NONE') {
              if (rawPermissions.includes('MANAGE_USERS')) {
                level = 'MANAGE';
              } else if (rawPermissions.includes('EDIT_USERS')) {
                level = 'EDIT';
              } else if (rawPermissions.includes('VIEW_USERS')) {
                level = 'VIEW';
              } else if (typeof permission.roleName === 'string') {
                const normalizedRole = permission.roleName.toUpperCase();
                if (['USER_MANAGER', 'ADMIN', 'OWNER'].includes(normalizedRole)) {
                  level = 'MANAGE';
                } else if (['USER_EDITOR', 'EDITOR'].includes(normalizedRole)) {
                  level = 'EDIT';
                } else if (['USER_VIEWER', 'VIEWER'].includes(normalizedRole)) {
                  level = 'VIEW';
                }
              }
            }

            return {
              moduleKey,
              moduleLabel: permission.moduleLabel ?? permission.label ?? permission.moduleName,
              level,
              assignmentId: permission.assignmentId ? String(permission.assignmentId) : undefined,
              roleName: permission.roleName,
              permissions: rawPermissions,
              companyId: permission.companyId ? String(permission.companyId) : undefined,
            };
          })
          .filter((permission: UserModulePermission) => permission.moduleKey.length > 0);

        const modulePermissions = ensureAdminUserModulePermission(
          normalizedModulePermissions,
          role,
        );

        return {
          id: String(user.id ?? ''),
          fullName: toStringOrFallback(user.name ?? user.fullName ?? user.email, 'Bilinmeyen Kullanıcı'),
          email: toStringOrFallback(user.email, ''),
          role,
          status: user.enabled === false ? 'INACTIVE' : 'ACTIVE',
          lastLoginAt: (user.lastLogin ?? user.lastLoginAt ?? null) as string | null,
          createdAt: (user.createDate ?? user.createdAt ?? null) as string | null,
          sessionTimeoutMinutes: typeof user.sessionTimeoutMinutes === 'number'
            ? user.sessionTimeoutMinutes
            : 15,
          modulePermissions,
        };
      })
    : [];

  return {
    items,
    total: typeof payload.total === 'number' ? payload.total : items.length,
    page: typeof payload.page === 'number' ? payload.page : params.page ?? 1,
    pageSize: typeof payload.pageSize === 'number' ? payload.pageSize : params.pageSize ?? items.length,
    meta: { reason: 'success' },
  };
};

export const fetchUserDetail = async (
  user: { id: string; email: string },
  scope?: RequestScope,
): Promise<UserDetail> => {
  if (shouldUseDevUsersFallback()) {
    return buildMockUserDetail(user);
  }

  const controlledConfig = buildControlledAccessRequestConfig(scope);
  const headers = controlledConfig.headers;

  if (shouldUseFetchTransportStub()) {
    try {
      const userResponse = await fetch(
        `${buildFetchGatewayUrl(USERS_RESOURCE_PATH)}/by-email?email=${encodeURIComponent(user.email)}`,
        { headers: headers as Record<string, string> },
      );
      if (!userResponse.ok) {
        if (UNAUTHORIZED_STATUS.has(userResponse.status)) {
          return buildFallbackUserDetail(user);
        }
        return buildFallbackUserDetail(user);
      }
      const userData = (await userResponse.json()) as UserDetailWire;
      let assignments: AssignmentWire[] = [];
      try {
        const permResponse = await fetch(
          `${buildFetchGatewayUrl(PERMISSIONS_RESOURCE_PATH)}/assignments?userId=${encodeURIComponent(user.id)}`,
          { headers: headers as Record<string, string> },
        );
        if (permResponse.ok) {
          const assignmentPayload = await permResponse.json();
          assignments = Array.isArray(assignmentPayload)
            ? assignmentPayload.filter(isPermissionWire).map((item) => item as AssignmentWire)
            : [];
        }
      } catch {
        // ignore; fallback handled below
      }
      return normalizeUserDetail(userData, assignments, user);
    } catch {
      return buildFallbackUserDetail(user);
    }
  }

  let userData: UserDetailWire;
  try {
    const client = resolveHttpClient();
    const response = await client.get<UserDetailWire>(
      `${USERS_RESOURCE_PATH}/by-email?email=${encodeURIComponent(user.email)}`,
      controlledConfig,
    );
    userData = response.data as UserDetailWire;
  } catch (error: unknown) {
    if (isAxiosError(error)) {
      const status = error.response?.status ?? 0;
      if (!error.response || UNAUTHORIZED_STATUS.has(status)) {
        console.warn('[usersApi] Kullanıcı detayı alınamadı, demo veri döndürülüyor.', error);
        return buildFallbackUserDetail(user);
      }
      const parsed = await parseErrorResponse(error);
      reportError('Kullanıcı bilgisi', parsed);
      throw new Error(parsed.message);
    }
    throw error;
  }

  let assignments: AssignmentWire[] = [];
  try {
    const client = resolveHttpClient();
    const response = await client.get<unknown>(
      `${PERMISSIONS_RESOURCE_PATH}/assignments?userId=${encodeURIComponent(user.id)}`,
      controlledConfig,
    );
    const assignmentPayload = response.data;
    assignments = Array.isArray(assignmentPayload)
      ? assignmentPayload.filter(isPermissionWire).map((item) => item as AssignmentWire)
      : [];
  } catch (error: unknown) {
    if (isAxiosError(error)) {
      const status = error.response?.status ?? 0;
      if (!UNAUTHORIZED_STATUS.has(status)) {
        console.warn('[usersApi] Yetki listesi alınamadı, boş devam ediliyor.', error);
      }
    } else {
      console.warn('[usersApi] Yetki listesi alınamadı, boş devam ediliyor.', error);
    }
  }

  return normalizeUserDetail(userData, assignments, user);
};

type UpdateUserPayload = {
  role?: string;
  enabled?: boolean;
  sessionTimeoutMinutes?: number;
};

export const updateUser = async (
  args: { userId: string; payload: UpdateUserPayload; scope?: RequestScope },
) => {
  try {
    const client = resolveHttpClient();
    const response = await client.put(
      `${USERS_RESOURCE_PATH}/${encodeURIComponent(args.userId)}`,
      args.payload,
      { headers: mergeHeaders(args.scope) },
    );
    return response.data;
  } catch (error: unknown) {
    const parsed = await parseErrorResponse(isAxiosError(error) ? error : undefined);
    reportError('Kullanıcı bilgisi güncelleme', parsed);
    throw new Error(parsed.message);
  }
};

export const updateUserRole = async (
  args: { userId: string; role: string; scope?: RequestScope },
) => updateUser({ userId: args.userId, payload: { role: args.role }, scope: args.scope });

const mapLevelToRole = (moduleKey: string, level: UserModuleAccessLevel): string => {
  const moduleRoles = MODULE_LEVEL_ROLE_MAP[moduleKey] ?? MODULE_LEVEL_ROLE_MAP.USER_MANAGEMENT;
  const roleName = moduleRoles[level];
  if (!roleName) {
    throw new Error('Bu modül için seçilen yetki seviyesi desteklenmiyor.');
  }
  return roleName;
};

export const updateUserModuleAccess = async (
  args: { userId: string; moduleKey: string; level: UserModuleAccessLevel; performedBy?: string; companyId?: string; allowGlobalScope?: boolean; scope?: RequestScope },
) => {
  const contextScope = args.scope ?? getStoredScope();
  const targetCompanyId = args.companyId;
  const payload: Record<string, unknown> = {
    userId: args.userId,
    companyId: targetCompanyId ?? undefined,
    projectId: contextScope.projectId,
    warehouseId: contextScope.warehouseId,
    roleName: mapLevelToRole(args.moduleKey, args.level),
  };
  if (args.performedBy !== undefined && args.performedBy !== null) {
    const numericPerformer = Number(args.performedBy);
    payload.performedBy = Number.isFinite(numericPerformer) ? numericPerformer : args.performedBy;
  }
  try {
    const client = resolveHttpClient();
    const response = await client.post(`${PERMISSIONS_RESOURCE_PATH}/assignments/update`, payload, {
      headers: mergeHeaders(args.scope),
    });
    return response.data;
  } catch (error: unknown) {
    const parsed = await parseErrorResponse(isAxiosError(error) ? error : undefined);
    reportError('Modül yetkisi güncelleme', parsed);
    throw new Error(parsed.message);
  }
};

export const revokeUserModuleAccess = async (
  args: { assignmentId: string; performedBy?: string; scope?: RequestScope },
) => {
  if (!args.assignmentId) {
    throw new Error('Atama bilgisi bulunamadı.');
  }
  const query = args.performedBy ? `?performedBy=${encodeURIComponent(args.performedBy)}` : '';
  try {
    const client = resolveHttpClient();
    await client.delete(
      `${PERMISSIONS_RESOURCE_PATH}/assignments/${encodeURIComponent(args.assignmentId)}${query}`,
      { headers: mergeHeaders(args.scope) },
    );
  } catch (error: unknown) {
    const parsed = await parseErrorResponse(isAxiosError(error) ? error : undefined);
    reportError('Modül yetkisi kaldırma', parsed);
    throw new Error(parsed.message);
  }
};

export const toggleUserStatus = async (
  args: { userId: string; enabled: boolean; scope?: RequestScope },
): Promise<UserMutationAck> => {
  try {
    const client = resolveHttpClient();
    const response = await client.put(
      `${USERS_RESOURCE_PATH}/${encodeURIComponent(args.userId)}/activation`,
      { active: args.enabled },
      { headers: mergeHeaders(args.scope) },
    );
    return response.data as UserMutationAck;
  } catch (error: unknown) {
    const parsed = await parseErrorResponse(isAxiosError(error) ? error : undefined);
    reportError('Kullanıcı durumu', parsed);
    throw new Error(parsed.message);
  }
};

export const triggerPasswordReset = async (
  args: { email: string },
) => {
  try {
    const client = resolveHttpClient();
    const response = await client.post(
      `${AUTH_RESOURCE_PATH}/password-resets`,
      { email: args.email },
      { headers: mergeHeaders() },
    );
    return response.data;
  } catch (error: unknown) {
    const parsed = await parseErrorResponse(isAxiosError(error) ? error : undefined);
    reportError('Parola sıfırlama', parsed);
    throw new Error(parsed.message);
  }
};
