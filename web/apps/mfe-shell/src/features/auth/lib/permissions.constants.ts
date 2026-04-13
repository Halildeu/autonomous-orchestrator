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
 * Legacy PERMISSIONS removed — all access checks now use MODULE_KEYS
 * with usePermissions().hasModule() from @mfe/auth.
 * See: STORY-0318, Faz 5 cleanup.
 */
