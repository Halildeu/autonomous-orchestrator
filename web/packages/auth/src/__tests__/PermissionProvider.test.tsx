// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { PermissionProvider, usePermissions } from '../PermissionProvider';
import type { AuthzMeResponse } from '../types';

const mockAuthzMe: AuthzMeResponse = {
  userId: '10',
  superAdmin: false,
  allowedModules: ['USER_MANAGEMENT'],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['TestRole'],
  modules: { USER_MANAGEMENT: 'VIEW' },
  actions: {},
  reports: {},
  pages: {},
  scopes: { companyIds: [1] },
  authzVersion: 5,
};

function createWrapper(httpGet: any, cacheTtl = 60_000) {
  return ({ children }: { children: React.ReactNode }) => (
    <PermissionProvider httpGet={httpGet} cacheTtl={cacheTtl}>
      {children}
    </PermissionProvider>
  );
}

describe('PermissionProvider version-based refresh', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('stores authzVersion from /me response', async () => {
    const httpGet = vi.fn().mockResolvedValue({ data: mockAuthzMe });

    const { result } = renderHook(() => usePermissions(), {
      wrapper: createWrapper(httpGet),
    });

    await waitFor(() => expect(result.current.initialized).toBe(true));
    expect(result.current.authz?.authzVersion).toBe(5);
  });

  it('does NOT call /me when version unchanged', async () => {
    const httpGet = vi.fn()
      .mockResolvedValueOnce({ data: mockAuthzMe }) // initial /me
      .mockResolvedValueOnce({ data: { authzVersion: 5 } }); // /version poll — same

    const { result } = renderHook(() => usePermissions(), {
      wrapper: createWrapper(httpGet, 1000),
    });

    await waitFor(() => expect(result.current.initialized).toBe(true));

    // httpGet called once for /me
    expect(httpGet).toHaveBeenCalledTimes(1);

    // Advance timer to trigger version poll
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });

    // Should have called /version but NOT /me again
    expect(httpGet).toHaveBeenCalledTimes(2);
    expect(httpGet).toHaveBeenLastCalledWith('/v1/authz/version');
  });

  it('calls /me when version changes', async () => {
    const updatedAuthz = { ...mockAuthzMe, authzVersion: 6 };
    const httpGet = vi.fn()
      .mockResolvedValueOnce({ data: mockAuthzMe }) // initial /me (v5)
      .mockResolvedValueOnce({ data: { authzVersion: 6 } }) // /version poll — changed!
      .mockResolvedValueOnce({ data: updatedAuthz }); // full /me refresh

    const { result } = renderHook(() => usePermissions(), {
      wrapper: createWrapper(httpGet, 1000),
    });

    await waitFor(() => expect(result.current.initialized).toBe(true));

    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });

    // Should have: /me (initial) + /version (poll) + /me (refresh) = 3 calls
    await waitFor(() => expect(httpGet).toHaveBeenCalledTimes(3));
  });

  it('falls back to full /me refresh when /version errors', async () => {
    const httpGet = vi.fn()
      .mockResolvedValueOnce({ data: mockAuthzMe }) // initial /me
      .mockRejectedValueOnce(new Error('network error')) // /version fails
      .mockResolvedValueOnce({ data: mockAuthzMe }); // fallback /me

    const { result } = renderHook(() => usePermissions(), {
      wrapper: createWrapper(httpGet, 1000),
    });

    await waitFor(() => expect(result.current.initialized).toBe(true));

    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });

    // fetchAuthzVersion returns -1 on error → triggers full /me
    await waitFor(() => expect(httpGet).toHaveBeenCalledTimes(3));
  });
});
