import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createZanzibarCache } from '../zanzibar-cache';

describe('ZanzibarCache', () => {
  let cache: ReturnType<typeof createZanzibarCache>;

  beforeEach(() => {
    cache = createZanzibarCache({ ttlMs: 5000, maxEntries: 10 });
    cache.updateVersion(1);
  });

  it('returns undefined on cache miss', () => {
    expect(cache.get('u1', 'can_view', 'report', 'r1')).toBeUndefined();
  });

  it('stores and retrieves entry', () => {
    cache.set('u1', 'can_view', 'report', 'r1', 'full', 'allowed');
    const entry = cache.get('u1', 'can_view', 'report', 'r1');
    expect(entry).toBeDefined();
    expect(entry!.access).toBe('full');
    expect(entry!.reason).toBe('allowed');
  });

  it('purges entire cache on version change', () => {
    cache.set('u1', 'can_view', 'report', 'r1', 'full', 'ok');
    cache.set('u1', 'can_edit', 'report', 'r2', 'disabled', 'denied');
    expect(cache.size).toBe(2);

    cache.updateVersion(2);
    expect(cache.size).toBe(0);
    expect(cache.get('u1', 'can_view', 'report', 'r1')).toBeUndefined();
  });

  it('does not purge on same version', () => {
    cache.set('u1', 'can_view', 'report', 'r1', 'full', 'ok');
    cache.updateVersion(1);
    expect(cache.size).toBe(1);
  });

  it('expires entries after TTL', () => {
    vi.useFakeTimers();
    cache.set('u1', 'can_view', 'report', 'r1', 'full', 'ok');
    expect(cache.get('u1', 'can_view', 'report', 'r1')).toBeDefined();

    vi.advanceTimersByTime(6000);
    expect(cache.get('u1', 'can_view', 'report', 'r1')).toBeUndefined();
    vi.useRealTimers();
  });

  it('evicts oldest on max capacity', () => {
    for (let i = 0; i < 10; i++) {
      cache.set('u1', 'can_view', 'report', `r${i}`, 'full', 'ok');
    }
    expect(cache.size).toBe(10);

    cache.set('u1', 'can_view', 'report', 'r10', 'full', 'ok');
    expect(cache.size).toBe(10);
    expect(cache.get('u1', 'can_view', 'report', 'r0')).toBeUndefined();
    expect(cache.get('u1', 'can_view', 'report', 'r10')).toBeDefined();
  });

  it('isolates different users', () => {
    cache.set('u1', 'can_view', 'report', 'r1', 'full', 'ok');
    cache.set('u2', 'can_view', 'report', 'r1', 'hidden', 'denied');
    expect(cache.get('u1', 'can_view', 'report', 'r1')!.access).toBe('full');
    expect(cache.get('u2', 'can_view', 'report', 'r1')!.access).toBe('hidden');
  });

  it('clear() empties all', () => {
    cache.set('u1', 'can_view', 'report', 'r1', 'full', 'ok');
    cache.clear();
    expect(cache.size).toBe(0);
  });
});
