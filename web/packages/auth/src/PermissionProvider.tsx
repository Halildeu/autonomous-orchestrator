import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import type { AuthzMeResponse, AccessLevel, GrantResult } from './types';
import { fetchAuthzMe } from './api';

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
  /** Cache TTL in ms (default: 60000 = 1 min) */
  cacheTtl?: number;
}

export function PermissionProvider({
  children,
  httpGet,
  permitAll = false,
  cacheTtl = 60_000,
}: PermissionProviderProps) {
  const [authz, setAuthz] = useState<AuthzMeResponse | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);

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
    } catch (err) {
      console.error('[PermissionProvider] Failed to fetch authz:', err);
      setAuthz(null);
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  }, [httpGet, permitAll]);

  useEffect(() => {
    loadAuthz();

    if (!permitAll && cacheTtl > 0) {
      const interval = setInterval(loadAuthz, cacheTtl);
      return () => clearInterval(interval);
    }
  }, [loadAuthz, permitAll, cacheTtl]);

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
