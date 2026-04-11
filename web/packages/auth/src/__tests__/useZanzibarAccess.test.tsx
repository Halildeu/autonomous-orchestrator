// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { PermissionProvider } from '../PermissionProvider';
import { useZanzibarAccess } from '../useZanzibarAccess';
import type { AuthzMeResponse } from '../types';

const baseAuthz: AuthzMeResponse = {
  userId: '10',
  superAdmin: false,
  allowedModules: ['AUDIT', 'REPORT'],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['TestRole'],
  modules: { AUDIT: 'VIEW', REPORT: 'MANAGE' },
  actions: { 'create_user': 'ALLOW', 'delete_user': 'DENY' },
  reports: { HR_REPORTS: 'ALLOW', FINANCE_REPORTS: 'DENY' },
  scopes: { companyIds: [1] },
  authzVersion: 5,
};

function createWrapper(overrides?: Partial<AuthzMeResponse>) {
  const authz = { ...baseAuthz, ...overrides };
  const httpGet = vi.fn().mockResolvedValue({ data: authz });
  return {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <PermissionProvider httpGet={httpGet} initialData={authz}>
        {children}
      </PermissionProvider>
    ),
    httpGet,
  };
}

describe('useZanzibarAccess — coarse gate (no server call)', () => {
  it('superAdmin always returns "full"', () => {
    const { wrapper } = createWrapper({ superAdmin: true });
    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'HR_REPORTS'),
      { wrapper }
    );
    expect(result.current.access).toBe('full');
    expect(result.current.loading).toBe(false);
    expect(result.current.reason).toBe('superadmin');
  });

  it('module not in /me → "hidden"', () => {
    const { wrapper } = createWrapper({ modules: { AUDIT: 'VIEW' } });
    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'module', 'WAREHOUSE'),
      { wrapper }
    );
    expect(result.current.access).toBe('hidden');
    expect(result.current.reason).toBe('no_module');
  });

  it('denied report → "hidden"', () => {
    const { wrapper } = createWrapper({ reports: { FINANCE_REPORTS: 'DENY' } });
    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'FINANCE_REPORTS'),
      { wrapper }
    );
    expect(result.current.access).toBe('hidden');
    expect(result.current.reason).toBe('no_report');
  });

  it('denied action → "disabled"', () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () => useZanzibarAccess('allowed', 'action', 'delete_user'),
      { wrapper }
    );
    expect(result.current.access).toBe('disabled');
    expect(result.current.reason).toBe('denied_action');
  });

  it('allowed action → "full"', () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () => useZanzibarAccess('allowed', 'action', 'create_user'),
      { wrapper }
    );
    expect(result.current.access).toBe('full');
    expect(result.current.reason).toBe('action_allowed');
  });
});

describe('useZanzibarAccess — server check', () => {
  it('calls server when coarse gate passes but needs object-level check', async () => {
    const { wrapper } = createWrapper();
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: true, reason: 'granted' },
    });

    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'HR_REPORTS', httpPost),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.access).toBe('readonly');
    expect(result.current.reason).toBe('granted');
    expect(httpPost).toHaveBeenCalledWith('/v1/authz/check', {
      relation: 'can_view',
      objectType: 'report',
      objectId: 'HR_REPORTS',
    });
  });

  it('can_edit relation → "full" access', async () => {
    const { wrapper } = createWrapper();
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: true, reason: 'granted' },
    });

    const { result } = renderHook(
      () => useZanzibarAccess('can_edit', 'report', 'HR_REPORTS', httpPost),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.access).toBe('full');
  });

  it('can_manage relation → "full" access', async () => {
    const { wrapper } = createWrapper();
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: true, reason: 'granted' },
    });

    const { result } = renderHook(
      () => useZanzibarAccess('can_manage', 'module', 'AUDIT', httpPost),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.access).toBe('full');
  });

  it('blocked reason → "disabled"', async () => {
    const { wrapper } = createWrapper();
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: false, reason: 'blocked' },
    });

    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'HR_REPORTS', httpPost),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.access).toBe('disabled');
    expect(result.current.reason).toBe('blocked');
  });

  it('no_relation reason → "hidden"', async () => {
    const { wrapper } = createWrapper();
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: false, reason: 'no_relation' },
    });

    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'HR_REPORTS', httpPost),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.access).toBe('hidden');
    expect(result.current.reason).toBe('no_relation');
  });

  it('server error → "hidden" with error reason', async () => {
    const { wrapper } = createWrapper();
    const httpPost = vi.fn().mockRejectedValue(new Error('network error'));

    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'HR_REPORTS', httpPost),
      { wrapper }
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.access).toBe('hidden');
    expect(result.current.reason).toBe('error');
  });

  it('no httpPost provided → "readonly" fallback', () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(
      () => useZanzibarAccess('can_view', 'report', 'HR_REPORTS'),
      { wrapper }
    );
    expect(result.current.access).toBe('readonly');
    expect(result.current.reason).toBe('no_server_check');
  });
});
