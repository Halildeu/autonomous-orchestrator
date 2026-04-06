import { useMemo } from 'react';
import { usePermissions } from './PermissionProvider';
import type { AccessLevel } from './types';

interface CheckResult {
  allowed: boolean;
  reason: 'ALLOWED' | 'NO_ROLE' | 'DENIED_BY_ROLE' | 'NO_PERMISSION' | 'LOADING';
  details: {
    permissionType: string;
    permissionKey: string;
    grantType: string | null;
  };
}

/**
 * Check a specific permission locally from the cached /authz/me response.
 * For server-side explain with full details, use useExplainPermission instead.
 */
export function useCheckPermission(permissionType: string, permissionKey: string): CheckResult {
  const { authz, initialized, isSuperAdmin } = usePermissions();

  return useMemo((): CheckResult => {
    if (!initialized || !authz) {
      return { allowed: false, reason: 'LOADING', details: { permissionType, permissionKey, grantType: null } };
    }

    if (isSuperAdmin()) {
      return { allowed: true, reason: 'ALLOWED', details: { permissionType, permissionKey, grantType: 'SUPER_ADMIN' } };
    }

    const roles = authz.roles ?? [];
    if (roles.length === 0) {
      return { allowed: false, reason: 'NO_ROLE', details: { permissionType, permissionKey, grantType: null } };
    }

    const type = permissionType.toLowerCase();

    if (type === 'module') {
      const level = authz.modules?.[permissionKey] as AccessLevel | undefined;
      if (!level || level === 'NONE') {
        return { allowed: false, reason: 'NO_PERMISSION', details: { permissionType, permissionKey, grantType: level ?? null } };
      }
      return { allowed: true, reason: 'ALLOWED', details: { permissionType, permissionKey, grantType: level } };
    }

    if (type === 'action') {
      const grant = authz.actions?.[permissionKey];
      if (grant === 'DENY') {
        return { allowed: false, reason: 'DENIED_BY_ROLE', details: { permissionType, permissionKey, grantType: 'DENY' } };
      }
      if (grant === 'ALLOW') {
        return { allowed: true, reason: 'ALLOWED', details: { permissionType, permissionKey, grantType: 'ALLOW' } };
      }
      return { allowed: false, reason: 'NO_PERMISSION', details: { permissionType, permissionKey, grantType: null } };
    }

    if (type === 'report') {
      const grant = authz.reports?.[permissionKey];
      if (grant === 'DENY') {
        return { allowed: false, reason: 'DENIED_BY_ROLE', details: { permissionType, permissionKey, grantType: 'DENY' } };
      }
      if (grant === 'ALLOW' || grant === undefined) {
        return { allowed: true, reason: 'ALLOWED', details: { permissionType, permissionKey, grantType: grant ?? 'IMPLICIT' } };
      }
      return { allowed: false, reason: 'NO_PERMISSION', details: { permissionType, permissionKey, grantType: null } };
    }

    if (type === 'page') {
      const grant = authz.pages?.[permissionKey];
      if (grant === 'DENY') {
        return { allowed: false, reason: 'DENIED_BY_ROLE', details: { permissionType, permissionKey, grantType: 'DENY' } };
      }
      if (grant === 'ALLOW' || grant === undefined) {
        return { allowed: true, reason: 'ALLOWED', details: { permissionType, permissionKey, grantType: grant ?? 'IMPLICIT' } };
      }
      return { allowed: false, reason: 'NO_PERMISSION', details: { permissionType, permissionKey, grantType: null } };
    }

    return { allowed: false, reason: 'NO_PERMISSION', details: { permissionType, permissionKey, grantType: null } };
  }, [authz, initialized, isSuperAdmin, permissionType, permissionKey]);
}
