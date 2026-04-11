import React from 'react';
import { useZanzibarAccess } from './useZanzibarAccess';

interface ZanzibarGateProps {
  /** OpenFGA relation to check: "can_view" | "can_edit" | "can_manage" */
  relation: string;
  /** OpenFGA object type: "report" | "module" | "action" | "company" */
  objectType: string;
  /** OpenFGA object ID: "HR_REPORTS" | "AUDIT" | "1" */
  objectId: string;
  /** Content to render when authorized */
  children: React.ReactNode;
  /** Fallback when access is hidden/denied (default: null = render nothing) */
  fallback?: React.ReactNode;
  /** Fallback during async server check (default: null = render nothing) */
  loadingFallback?: React.ReactNode;
  /** HTTP POST function for server checks */
  httpPost?: (url: string, body: any) => Promise<{ data: any }>;
}

/**
 * Object-level authorization gate — 3 katmanlı Zanzibar-Aware yapı (Katman 2).
 * CNS-20260411-005 uzlaşısı: ZanzibarGate wraps children with object-level check.
 *
 * Usage:
 *   <ZanzibarGate relation="can_view" objectType="report" objectId="HR_REPORTS">
 *     <ReportDashboard />
 *   </ZanzibarGate>
 */
export function ZanzibarGate({
  relation,
  objectType,
  objectId,
  children,
  fallback = null,
  loadingFallback = null,
  httpPost,
}: ZanzibarGateProps) {
  const { access, loading } = useZanzibarAccess(relation, objectType, objectId, httpPost);

  if (loading) return <>{loadingFallback}</>;
  if (access === 'hidden') return <>{fallback}</>;

  return <>{children}</>;
}
