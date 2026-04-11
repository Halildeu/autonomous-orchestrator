/**
 * Object-level Zanzibar permission cache.
 *
 * Cache key: userId + relation + objectType + objectId + authzVersion.
 * TTL is backstop only (30s default). Primary invalidation is authzVersion-based.
 *
 * Codex consensus (CNS-20260411-005):
 * - /me snapshot is bounded hint, NOT authoritative for object-level
 * - authzVersion drives cache invalidation (not TTL alone)
 * - When authzVersion changes, entire cache is purged
 */

export interface ZanzibarCacheEntry {
  access: string;
  reason: string;
  checkedAt: number;
  authzVersion: number;
}

export interface ZanzibarCacheConfig {
  /** TTL backstop in milliseconds. Default: 30000 (30s). */
  ttlMs: number;
  /** Maximum entries before eviction. Default: 500. */
  maxEntries: number;
}

const DEFAULT_CONFIG: ZanzibarCacheConfig = {
  ttlMs: 30_000,
  maxEntries: 500,
};

function buildKey(
  userId: string,
  relation: string,
  objectType: string,
  objectId: string,
): string {
  return `${userId}:${relation}:${objectType}:${objectId}`;
}

/**
 * Create an object-level permission cache instance.
 * Typically created once per app and passed to ZanzibarCacheProvider.
 */
export function createZanzibarCache(config: Partial<ZanzibarCacheConfig> = {}) {
  const { ttlMs, maxEntries } = { ...DEFAULT_CONFIG, ...config };
  const store = new Map<string, ZanzibarCacheEntry>();
  let currentVersion = -1;

  return {
    get(
      userId: string,
      relation: string,
      objectType: string,
      objectId: string,
    ): ZanzibarCacheEntry | undefined {
      const key = buildKey(userId, relation, objectType, objectId);
      const entry = store.get(key);
      if (!entry) return undefined;

      // Version mismatch — stale
      if (entry.authzVersion !== currentVersion) {
        store.delete(key);
        return undefined;
      }

      // TTL backstop
      if (Date.now() - entry.checkedAt > ttlMs) {
        store.delete(key);
        return undefined;
      }

      return entry;
    },

    set(
      userId: string,
      relation: string,
      objectType: string,
      objectId: string,
      access: string,
      reason: string,
    ): void {
      const key = buildKey(userId, relation, objectType, objectId);

      if (store.size >= maxEntries && !store.has(key)) {
        const firstKey = store.keys().next().value;
        if (firstKey !== undefined) store.delete(firstKey);
      }

      store.set(key, {
        access,
        reason,
        checkedAt: Date.now(),
        authzVersion: currentVersion,
      });
    },

    /** Update authzVersion. Purges cache if version changed. */
    updateVersion(newVersion: number): void {
      if (newVersion !== currentVersion && newVersion > 0) {
        store.clear();
        currentVersion = newVersion;
      }
    },

    get size() { return store.size; },
    get version() { return currentVersion; },
    clear(): void { store.clear(); },
  };
}

export type ZanzibarCache = ReturnType<typeof createZanzibarCache>;
