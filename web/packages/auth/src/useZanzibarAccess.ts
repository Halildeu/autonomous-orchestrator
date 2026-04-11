import { useMemo, useEffect, useState } from 'react';
import { usePermissions } from './PermissionProvider';
import { checkPermission } from './api';
import type { ZanzibarAccessLevel, CheckResponse } from './types';

interface ZanzibarAccessResult {
  /** Design-system compatible access level */
  access: ZanzibarAccessLevel;
  /** Whether an async server check is in progress */
  loading: boolean;
  /** Human-readable reason for the access decision */
  reason: string;
}

/**
 * Object-level authorization hook — 3 katmanlı Zanzibar-Aware yapı (Katman 3).
 * CNS-20260411-005 uzlaşısı: coarse gate (/me) + object-level (server) + reason field.
 *
 * Strategy:
 * 1. Coarse gate: Check /me cache for quick module/report/action decisions (no network)
 * 2. Object-level: If coarse gate can't resolve, call /v1/authz/check with reason
 * 3. Map server response to ZanzibarAccessLevel (full/readonly/disabled/hidden)
 *
 * @param relation  - OpenFGA relation: "can_view" | "can_edit" | "can_manage"
 * @param objectType - OpenFGA object type: "report" | "module" | "action" | "company"
 * @param objectId  - OpenFGA object ID: "HR_REPORTS" | "AUDIT" | "1"
 * @param httpPost  - HTTP POST function for server checks (optional; skips server check if not provided)
 */
export function useZanzibarAccess(
  relation: string,
  objectType: string,
  objectId: string,
  httpPost?: (url: string, body: any) => Promise<{ data: any }>
): ZanzibarAccessResult {
  const { authz, initialized, isSuperAdmin, hasModule, canViewReport, isActionAllowed } = usePermissions();
  const [serverResult, setServerResult] = useState<CheckResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Phase 1: Coarse gate — quick decision from /me cache (no network)
  const coarseResult = useMemo((): { access: ZanzibarAccessLevel | null; skip: boolean; reason: string } => {
    if (!initialized) return { access: null, skip: true, reason: 'loading' };
    if (isSuperAdmin()) return { access: 'full', skip: true, reason: 'superadmin' };

    if (objectType === 'module') {
      if (!hasModule(objectId)) return { access: 'hidden', skip: true, reason: 'no_module' };
    }
    if (objectType === 'report') {
      if (!canViewReport(objectId)) return { access: 'hidden', skip: true, reason: 'no_report' };
    }
    if (objectType === 'action') {
      if (!isActionAllowed(objectId)) return { access: 'disabled', skip: true, reason: 'denied_action' };
      return { access: 'full', skip: true, reason: 'action_allowed' };
    }

    // Coarse gate can't resolve — need server check
    return { access: null, skip: false, reason: '' };
  }, [initialized, isSuperAdmin, hasModule, canViewReport, isActionAllowed, objectType, objectId]);

  // Phase 2: Object-level server check (only if coarse gate didn't resolve)
  useEffect(() => {
    if (coarseResult.skip || !httpPost) {
      setServerResult(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    checkPermission(httpPost, { relation, objectType, objectId })
      .then((res) => {
        if (!cancelled) setServerResult(res);
      })
      .catch(() => {
        if (!cancelled) setServerResult({ allowed: false, reason: 'error' });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [coarseResult.skip, relation, objectType, objectId, httpPost]);

  // Phase 3: Map to ZanzibarAccessLevel
  return useMemo((): ZanzibarAccessResult => {
    // Coarse gate resolved
    if (coarseResult.skip && coarseResult.access != null) {
      return { access: coarseResult.access, loading: false, reason: coarseResult.reason };
    }

    // Waiting for initialization or server check
    if (!initialized) {
      return { access: 'hidden', loading: true, reason: 'loading' };
    }

    // No httpPost provided — can't do server check, grant based on coarse gate pass
    if (!httpPost) {
      return { access: 'readonly', loading: false, reason: 'no_server_check' };
    }

    // Server check in progress
    if (!serverResult) {
      return { access: 'hidden', loading: true, reason: 'checking' };
    }

    // Server check completed — map reason to access level
    if (serverResult.allowed) {
      const level: ZanzibarAccessLevel =
        relation.includes('manage') ? 'full' :
        relation.includes('edit') ? 'full' :
        'readonly';
      return { access: level, loading: false, reason: serverResult.reason ?? 'granted' };
    }

    // Denied — distinguish blocked (disabled) from no_relation (hidden)
    const access: ZanzibarAccessLevel = serverResult.reason === 'blocked' ? 'disabled' : 'hidden';
    return { access, loading: false, reason: serverResult.reason ?? 'denied' };
  }, [coarseResult, initialized, httpPost, serverResult, relation]);
}
