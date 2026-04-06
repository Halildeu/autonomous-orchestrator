// @mfe/auth — Centralized authorization package for ERP MFE apps.
// All permission checks should go through this package.

export { PermissionProvider, usePermissions } from './PermissionProvider';
export { useHasModule, useIsSuperAdmin } from './useHasPermission';
export { useCheckPermission } from './useCheckPermission';
export { useExplainPermission } from './useExplainPermission';
export { ProtectedRoute, ProtectedSection } from './ProtectedRoute';
export { fetchAuthzMe, checkPermission } from './api';
export { MODULES } from './types';
export type {
  AuthzMeResponse, CheckRequest, CheckResponse, ModuleKey,
  AccessLevel, GrantResult, ScopeAssignment, ExplainResponse,
  PermissionCatalog, ModuleCatalogItem, ActionCatalogItem, ReportCatalogItem, PageCatalogItem,
} from './types';
export { useAuthorization } from './compat';
