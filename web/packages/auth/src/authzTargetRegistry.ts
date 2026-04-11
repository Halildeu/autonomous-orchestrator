/**
 * AuthzTarget Registry — maps report groups to OpenFGA object references.
 * CNS-20260411-003 #3: Codex accepted — authzTarget {objectType, objectId} instead of reportGroup string.
 *
 * Used by canViewReport (deny-default) and future batch-check adoption.
 */

export interface AuthzTarget {
  objectType: string;
  objectId: string;
  label: string;
}

/**
 * Report group → OpenFGA authzTarget mapping.
 * Keys match backend PermissionDataInitializer report group keys (reports.* prefix stripped).
 */
export const REPORT_AUTHZ_TARGETS: Record<string, AuthzTarget> = {
  HR_REPORTS: { objectType: 'report', objectId: 'hr_reports', label: 'HR Reports' },
  FINANCE_REPORTS: { objectType: 'report', objectId: 'finance_reports', label: 'Finance Reports' },
  SALES_REPORTS: { objectType: 'report', objectId: 'sales_reports', label: 'Sales Reports' },
  ANALYTICS_REPORTS: { objectType: 'report', objectId: 'analytics_reports', label: 'Analytics Reports' },
} as const;

export type ReportGroupKey = keyof typeof REPORT_AUTHZ_TARGETS;

/**
 * Resolve an authzTarget for a given report group key.
 * Returns undefined if the key is not in the registry.
 */
export function getReportAuthzTarget(reportKey: string): AuthzTarget | undefined {
  return REPORT_AUTHZ_TARGETS[reportKey];
}
