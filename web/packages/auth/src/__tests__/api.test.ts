// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { checkPermission, checkPermissionBatch } from '../api';

describe('checkPermission — reason-aware (CNS-20260411-005)', () => {
  it('returns full CheckResponse with reason', async () => {
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: true, reason: 'granted' },
    });

    const result = await checkPermission(httpPost, {
      relation: 'can_view',
      objectType: 'report',
      objectId: 'HR_REPORTS',
    });

    expect(result.allowed).toBe(true);
    expect(result.reason).toBe('granted');
    expect(httpPost).toHaveBeenCalledWith('/v1/authz/check', {
      relation: 'can_view',
      objectType: 'report',
      objectId: 'HR_REPORTS',
    });
  });

  it('returns blocked reason when denied', async () => {
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: false, reason: 'blocked' },
    });

    const result = await checkPermission(httpPost, {
      relation: 'can_edit',
      objectType: 'report',
      objectId: 'FINANCE_REPORTS',
    });

    expect(result.allowed).toBe(false);
    expect(result.reason).toBe('blocked');
  });

  it('returns no_relation when no tuple exists', async () => {
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: false, reason: 'no_relation' },
    });

    const result = await checkPermission(httpPost, {
      relation: 'can_manage',
      objectType: 'module',
      objectId: 'UNKNOWN',
    });

    expect(result.allowed).toBe(false);
    expect(result.reason).toBe('no_relation');
  });

  it('propagates network errors', async () => {
    const httpPost = vi.fn().mockRejectedValue(new Error('network error'));

    await expect(
      checkPermission(httpPost, { relation: 'can_view', objectType: 'report', objectId: 'X' })
    ).rejects.toThrow('network error');
  });
});

describe('checkPermissionBatch', () => {
  it('returns array of results', async () => {
    const httpPost = vi.fn().mockResolvedValue({
      data: {
        results: [
          { allowed: true, reason: 'granted', relation: 'can_view', objectType: 'report', objectId: 'HR' },
          { allowed: false, reason: 'blocked', relation: 'can_edit', objectType: 'report', objectId: 'FIN' },
          { allowed: false, reason: 'no_relation', relation: 'can_manage', objectType: 'module', objectId: 'X' },
        ],
      },
    });

    const results = await checkPermissionBatch(httpPost, [
      { relation: 'can_view', objectType: 'report', objectId: 'HR' },
      { relation: 'can_edit', objectType: 'report', objectId: 'FIN' },
      { relation: 'can_manage', objectType: 'module', objectId: 'X' },
    ]);

    expect(results).toHaveLength(3);
    expect(results[0].allowed).toBe(true);
    expect(results[0].reason).toBe('granted');
    expect(results[1].allowed).toBe(false);
    expect(results[1].reason).toBe('blocked');
    expect(results[2].reason).toBe('no_relation');

    expect(httpPost).toHaveBeenCalledWith('/v1/authz/check/batch', {
      checks: [
        { relation: 'can_view', objectType: 'report', objectId: 'HR' },
        { relation: 'can_edit', objectType: 'report', objectId: 'FIN' },
        { relation: 'can_manage', objectType: 'module', objectId: 'X' },
      ],
    });
  });

  it('handles empty batch', async () => {
    const httpPost = vi.fn().mockResolvedValue({
      data: { results: [] },
    });

    const results = await checkPermissionBatch(httpPost, []);
    expect(results).toHaveLength(0);
  });
});
