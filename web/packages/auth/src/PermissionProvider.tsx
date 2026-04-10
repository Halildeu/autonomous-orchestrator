import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import type { AuthzMeResponse, AccessLevel, GrantResult } from './types';
import { fetchAuthzMe, fetchAuthzVersion } from './api';

interface PermissionContextValue {
  /** Current user's authorization data */
  authz: AuthzMeResponse | null;
  /** Whether initial load is complete */
  initialized: boolean;
  /** Whether currently loading */
  loading: boolean;
  /** Check if user has access to a module */
  hasModule: (module: string) => boolean;
  /** Get module access level (VIEW | MANAGE | NONE) */
  getModuleLevel: (module: string) => AccessLevel;
  /** Check if an action is allowed */
  isActionAllowed: (action: string) => boolean;
  /** Check if an action is explicitly denied */
  isActionDenied: (action: string) => boolean;
  /** Check if user can view a report */
  canViewReport: (report: string) => boolean;
  /** Check if user can access a page */
  canAccessPage: (page: string) => boolean;
  /** Get user's role names */
  getUserRoles: () => string[];
  /** Check if user is superAdmin */
  isSuperAdmin: () => boolean;
  /** Check if user can access a company */
  canAccessCompany: (companyId: number) => boolean;
  /** Refresh authorization data */
  refresh: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextValue>({
  authz: null,
  initialized: false,
  loading: false,
  hasModule: () => false,
  getModuleLevel: () => 'NONE',
  isActionAllowed: () => false,
  isActionDenied: () => false,
  canViewReport: () => false,
  canAccessPage: () => false,
  getUserRoles: () => [],
  isSuperAdmin: () => false,
  canAccessCompany: () => false,
  refresh: async () => {},
});

interface PermissionProviderProps {
  children: React.ReactNode;
  /** HTTP GET function (from shared-http or axios) */
  httpGet: (url: string) => Promise<{ data: any }>;
  /** If true, all permissions are granted (dev/permitAll mode) */
  permitAll?: boolean;
  /** If false, authz isteği atılmaz; token beklenir. */
  enabled?: boolean;
  /** Cache TTL in ms (default: 60000 = 1 min) */
  cacheTtl?: number;
  /** Pre-fetched authz data — skips initial /me fetch when provided. */
  initialData?: AuthzMeResponse | null;
}

export function PermissionProvider({
  children,
  httpGet,
  permitAll = false,
  enabled = true,
  cacheTtl = 60_000,
  initialData,
}: PermissionProviderProps) {
  const [authz, setAuthz] = useState<AuthzMeResponse | null>(initialData ?? null);
  const [initialized, setInitialized] = useState(!!initialData);
  const [loading, setLoading] = useState(false);
  const lastVersionRef = React.useRef<number | null>(initialData?.authzVersion ?? null);

  const loadAuthz = useCallback(async () => {
    if (permitAll) {
      setAuthz({
        userId: 'dev-user',
        superAdmin: true,
        allowedModules: [
          'USER_MANAGEMENT', 'ACCESS', 'AUDIT', 'REPORT',
          'WAREHOUSE', 'PURCHASE', 'THEME',
        ],
        allowedCompanyIds: [],
        allowedProjectIds: [],
        allowedWarehouseIds: [],
        roles: ['Süper Admin'],
        modules: {
          USER_MANAGEMENT: 'MANAGE', ACCESS: 'MANAGE', AUDIT: 'MANAGE',
          REPORT: 'MANAGE', WAREHOUSE: 'MANAGE', PURCHASE: 'MANAGE', THEME: 'MANAGE',
        },
        actions: {},
        reports: {},
        pages: {},
        scopes: { companyIds: [], projectIds: [], warehouseIds: [], branchIds: [] },
      });
      setInitialized(true);
      return;
    }

    setLoading(true);
    try {
      const data = await fetchAuthzMe(httpGet);
      setAuthz(data);
      setInitialized(true);
      if (data.authzVersion != null) {
        lastVersionRef.current = data.authzVersion;
      }
    } catch (err) {
      console.error('[PermissionProvider] Failed to fetch authz:', err);
      // Do NOT set initialized=true on failure — keep loading state so
      // ProtectedRoute shows loading spinner instead of redirecting to unauthorized.
      // The periodic refresh (60s) or initialData from AuthBootstrapper will recover.
      setAuthz(null);
    } finally {
      setLoading(false);
    }
  }, [httpGet, permitAll]);

  useEffect(() => {
    if (!enabled) {
      // Don't set initialized=true when disabled — ProtectedRoute should
      // keep showing loading until auth init completes and enables us.
      setAuthz(null);
      setLoading(false);
      return undefined;
    }

    // If parent provides pre-fetched data, use it instead of fetching
    if (initialData) {
      setAuthz(initialData);
      setInitialized(true);
    } else {
      loadAuthz();
    }

    // P0: Version-based smart refresh — poll /version (lightweight),
    // only do full /me refresh when version changes.
    if (!permitAll && cacheTtl > 0) {
      const pollVersion = async () => {
        try {
          const serverVersion = await fetchAuthzVersion(httpGet);
          if (serverVersion === -1) {
            await loadAuthz();
            return;
          }
          if (lastVersionRef.current === null || serverVersion !== lastVersionRef.current) {
            await loadAuthz();
          }
        } catch {
          // Silently skip — next poll will retry
        }
      };
      const interval = setInterval(pollVersion, cacheTtl);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [loadAuthz, httpGet, permitAll, enabled, cacheTtl, initialData]);

  const value = useMemo<PermissionContextValue>(() => ({
    authz,
    initialized,
    loading,
    hasModule: (module: string) => {
      if (permitAll || authz?.superAdmin) return true;
      // Prefer new modules map, fallback to legacy allowedModules
      if (authz?.modules && Object.keys(authz.modules).length > 0) {
        const level = authz.modules[module];
        return level === 'VIEW' || level === 'MANAGE';
      }
      return authz?.allowedModules?.includes(module) ?? false;
    },
    getModuleLevel: (module: string): AccessLevel => {
      if (permitAll || authz?.superAdmin) return 'MANAGE';
      return (authz?.modules?.[module] as AccessLevel) ?? 'NONE';
    },
    isActionAllowed: (action: string) => {
      if (permitAll || authz?.superAdmin) return true;
      return authz?.actions?.[action] === 'ALLOW';
    },
    isActionDenied: (action: string) => {
      return authz?.actions?.[action] === 'DENY';
    },
    canViewReport: (report: string) => {
      if (permitAll || authz?.superAdmin) return true;
      const grant = authz?.reports?.[report];
      return grant === 'ALLOW' || grant === undefined; // undefined = not restricted
    },
    canAccessPage: (page: string) => {
      if (permitAll || authz?.superAdmin) return true;
      const grant = authz?.pages?.[page];
      return grant === 'ALLOW' || grant === undefined;
    },
    getUserRoles: () => authz?.roles ?? [],
    isSuperAdmin: () => permitAll || (authz?.superAdmin ?? false),
    canAccessCompany: (companyId: number) => {
      if (permitAll || authz?.superAdmin) return true;
      return authz?.allowedCompanyIds?.includes(companyId) ?? false;
    },
    refresh: loadAuthz,
  }), [authz, initialized, loading, permitAll, loadAuthz]);

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}

/**
 * Hook to access permission context.
 */
export function usePermissions() {
  return useContext(PermissionContext);
}
