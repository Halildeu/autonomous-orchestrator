/**
 * Authorization types matching backend AuthzControllerV1 DTOs.
 * STORY-0318: Enhanced with roles, modules, actions, reports, pages, scopes.
 */

export interface AuthzMeResponse {
  userId: string;
  superAdmin: boolean;

  // Legacy fields (backward compat)
  permissions?: string[];
  allowedModules: string[];
  allowedCompanyIds: number[];
  allowedProjectIds: number[];
  allowedWarehouseIds: number[];

  // STORY-0318: Enhanced fields
  roles?: string[];
  modules?: Record<string, AccessLevel>;     // key → "VIEW" | "MANAGE"
  actions?: Record<string, GrantResult>;     // key → "ALLOW" | "DENY"
  reports?: Record<string, GrantResult>;     // key → "ALLOW" | "DENY"
  pages?: Record<string, GrantResult>;       // key → "ALLOW" | "DENY"
  scopes?: ScopeAssignment;
}

/** Access levels for modules. EDIT removed per K1. */
export type AccessLevel = 'NONE' | 'VIEW' | 'MANAGE';

/** Grant result for actions/reports/pages/fields. */
export type GrantResult = 'ALLOW' | 'DENY';

/** Scope assignment for data-level authorization. */
export interface ScopeAssignment {
  companyIds?: number[];
  projectIds?: number[];
  warehouseIds?: number[];
  branchIds?: number[];
}

export interface CheckRequest {
  relation: string;
  objectType: string;
  objectId: string;
}

export interface CheckResponse {
  allowed: boolean;
}

/** Explain response from /v1/authz/explain. */
export interface ExplainResponse {
  allowed: boolean;
  reason: 'ALLOWED' | 'NO_ROLE' | 'DENIED_BY_ROLE' | 'NO_SCOPE' | 'NO_PERMISSION';
  details: {
    roleName: string | null;
    grantType: string | null;
    permissionType: string;
    permissionKey: string;
  };
  userRoles: string[];
  userScopes: Record<string, number[]>;
}

/** Permission catalog item types. */
export interface PermissionCatalog {
  modules: ModuleCatalogItem[];
  actions: ActionCatalogItem[];
  reports: ReportCatalogItem[];
  pages: PageCatalogItem[];
}

export interface ModuleCatalogItem {
  key: string;
  label: string;
  levels: AccessLevel[];
}

export interface ActionCatalogItem {
  key: string;
  label: string;
  module: string;
  deniable: boolean;
}

export interface ReportCatalogItem {
  key: string;
  label: string;
  module: string;
}

export interface PageCatalogItem {
  key: string;
  label: string;
  module: string;
}

/**
 * Module permission constants matching OpenFGA model.
 */
export const MODULES = {
  USER_MANAGEMENT: 'USER_MANAGEMENT',
  ACCESS: 'ACCESS',
  AUDIT: 'AUDIT',
  REPORT: 'REPORT',
  WAREHOUSE: 'WAREHOUSE',
  PURCHASE: 'PURCHASE',
  THEME: 'THEME',
} as const;

export type ModuleKey = keyof typeof MODULES;
