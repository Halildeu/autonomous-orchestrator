// @mfe/auth — Centralized authorization package for ERP MFE apps.
// All permission checks should go through this package.

export { PermissionProvider, usePermissions } from './PermissionProvider';
export { useHasModule, useIsSuperAdmin } from './useHasPermission';
export { useCheckPermission } from './useCheckPermission';
export { useExplainPermission } from './useExplainPermission';
export { ProtectedRoute, ProtectedSection } from './ProtectedRoute';
export { useZanzibarAccess } from './useZanzibarAccess';
export { useBatchZanzibarAccess } from './useBatchZanzibarAccess';
export type { BatchAccessEntry, BatchZanzibarAccessResult } from './useBatchZanzibarAccess';
export { ZanzibarGate } from './ZanzibarGate';
export { fetchAuthzMe, fetchAuthzVersion, checkPermission, checkPermissionBatch } from './api';
export { MODULES } from './types';
export { REPORT_AUTHZ_TARGETS, getReportAuthzTarget } from './authzTargetRegistry';
export type { AuthzTarget, ReportGroupKey } from './authzTargetRegistry';
export type {
  AuthzMeResponse, CheckRequest, CheckResponse, ModuleKey,
  AccessLevel, GrantResult, ScopeAssignment, ExplainResponse,
  PermissionCatalog, ModuleCatalogItem, ActionCatalogItem, ReportCatalogItem,
  CheckReason, BatchCheckRequest, BatchCheckItem, BatchCheckResponse,
  ZanzibarAccessLevel,
} from './types';
// Object-level permission cache (authzVersion-driven)
export { createZanzibarCache } from './zanzibar-cache';
export type { ZanzibarCache, ZanzibarCacheConfig, ZanzibarCacheEntry } from './zanzibar-cache';
