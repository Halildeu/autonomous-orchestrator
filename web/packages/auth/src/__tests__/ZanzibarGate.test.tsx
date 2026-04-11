// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { PermissionProvider } from '../PermissionProvider';
import { ZanzibarGate } from '../ZanzibarGate';
import type { AuthzMeResponse } from '../types';

const superAdminAuthz: AuthzMeResponse = {
  userId: '1',
  superAdmin: true,
  allowedModules: ['AUDIT'],
  allowedCompanyIds: [],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['Admin'],
  modules: { AUDIT: 'MANAGE' },
  actions: {},
  reports: {},
  scopes: {},
  authzVersion: 1,
};

const restrictedAuthz: AuthzMeResponse = {
  userId: '2',
  superAdmin: false,
  allowedModules: [],
  allowedCompanyIds: [],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['Viewer'],
  modules: {},
  actions: {},
  reports: { HR_REPORTS: 'DENY' },
  scopes: {},
  authzVersion: 1,
};

function createWrapper(authz: AuthzMeResponse) {
  const httpGet = vi.fn().mockResolvedValue({ data: authz });
  return ({ children }: { children: React.ReactNode }) => (
    <PermissionProvider httpGet={httpGet} initialData={authz}>
      {children}
    </PermissionProvider>
  );
}

describe('ZanzibarGate', () => {
  it('renders children when superAdmin', () => {
    render(
      <ZanzibarGate relation="can_view" objectType="report" objectId="HR_REPORTS">
        <div data-testid="protected-content">Protected Content</div>
      </ZanzibarGate>,
      { wrapper: createWrapper(superAdminAuthz) }
    );

    expect(screen.getByTestId('protected-content')).toBeInTheDocument();
  });

  it('renders fallback when report is denied', () => {
    render(
      <ZanzibarGate
        relation="can_view"
        objectType="report"
        objectId="HR_REPORTS"
        fallback={<div data-testid="access-denied">Access Denied</div>}
      >
        <div data-testid="protected-content">Protected Content</div>
      </ZanzibarGate>,
      { wrapper: createWrapper(restrictedAuthz) }
    );

    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    expect(screen.getByTestId('access-denied')).toBeInTheDocument();
  });

  it('renders nothing by default when hidden (no fallback)', () => {
    const { container } = render(
      <ZanzibarGate relation="can_view" objectType="module" objectId="WAREHOUSE">
        <div data-testid="protected-content">Protected Content</div>
      </ZanzibarGate>,
      { wrapper: createWrapper(restrictedAuthz) }
    );

    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    expect(container.innerHTML).toBe('');
  });

  it('renders loadingFallback during server check', async () => {
    const httpPost = vi.fn().mockImplementation(
      () => new Promise(() => {}) // never resolves — simulates loading
    );

    const authz: AuthzMeResponse = {
      ...restrictedAuthz,
      reports: { HR_REPORTS: 'ALLOW' }, // passes coarse gate → triggers server check
    };

    render(
      <ZanzibarGate
        relation="can_view"
        objectType="report"
        objectId="HR_REPORTS"
        httpPost={httpPost}
        loadingFallback={<div data-testid="loading">Loading...</div>}
      >
        <div data-testid="protected-content">Protected Content</div>
      </ZanzibarGate>,
      { wrapper: createWrapper(authz) }
    );

    // Should show loading fallback while server check is pending
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
  });

  it('renders children after successful server check', async () => {
    const httpPost = vi.fn().mockResolvedValue({
      data: { allowed: true, reason: 'granted' },
    });

    const authz: AuthzMeResponse = {
      ...restrictedAuthz,
      reports: { HR_REPORTS: 'ALLOW' },
    };

    render(
      <ZanzibarGate
        relation="can_view"
        objectType="report"
        objectId="HR_REPORTS"
        httpPost={httpPost}
      >
        <div data-testid="protected-content">Protected Content</div>
      </ZanzibarGate>,
      { wrapper: createWrapper(authz) }
    );

    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument();
    });
  });
});
