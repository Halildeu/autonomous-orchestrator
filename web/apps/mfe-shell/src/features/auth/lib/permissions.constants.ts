/**
 * OpenFGA module keys — matches backend PermissionCatalogService.
 * Used with usePermissions().hasModule() from @mfe/auth.
 *
 * @deprecated Legacy string constants below kept for backward compat.
 * Prefer MODULE_KEYS for new code.
 */
export const MODULE_KEYS = {
  USER_MANAGEMENT: 'USER_MANAGEMENT',
  ACCESS: 'ACCESS',
  AUDIT: 'AUDIT',
  REPORT: 'REPORT',
  WAREHOUSE: 'WAREHOUSE',
  PURCHASE: 'PURCHASE',
  THEME: 'THEME',
} as const;

export type ModuleKey = keyof typeof MODULE_KEYS;

/**
 * @deprecated Use MODULE_KEYS with usePermissions().hasModule() instead.
 * Kept for backward compatibility during migration.
 */
export const PERMISSIONS = {
  USER_MANAGEMENT_MODULE: 'user-read',
  USER_MANAGEMENT_EDIT: 'user-update',
  USER_MANAGEMENT_RESET_PASSWORD: 'user-update',
  USER_MANAGEMENT_TOGGLE_STATUS: 'user-update',
  ACCESS_MODULE: 'access-read',
  AUDIT_MODULE: 'audit-read',
  REPORTING_MODULE: 'VIEW_REPORTS',
  THEME_ADMIN: 'THEME_ADMIN',
} as const;

export type PermissionKey = keyof typeof PERMISSIONS;
