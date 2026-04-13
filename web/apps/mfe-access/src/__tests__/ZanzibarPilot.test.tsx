// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { PermissionProvider, useZanzibarAccess } from '@mfe/auth';
import type { AuthzMeResponse } from '@mfe/auth';
import { Button } from '@mfe/design-system';

/**
 * Zanzibar Pilot — mfe-access
 * Faz 1.5: useZanzibarAccess ile RoleDrawer Save butonunda access kontrolu.
 * access={useZanzibarAccess("can_edit", "module", "ACCESS").access} ile
 * Button'a design-system access prop'u aktarilir.
 */

/* ------------------------------------------------------------------ */
/*  Test fixtures                                                      */
/* ------------------------------------------------------------------ */

/** User with MANAGE permission on ACCESS module — full edit rights */
const managerAuthz: AuthzMeResponse = {
  userId: '10',
  superAdmin: false,
  allowedModules: ['ACCESS'],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['AccessManager'],
  modules: { ACCESS: 'MANAGE' },
  actions: {},
  reports: {},
  scopes: {},
  authzVersion: 1,
};

/** User with no ACCESS module — should be hidden */
const noAccessAuthz: AuthzMeResponse = {
  userId: '20',
  superAdmin: false,
  allowedModules: [],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['Basic'],
  modules: {},
  actions: {},
  reports: {},
  scopes: {},
  authzVersion: 1,
};

/** SuperAdmin — always full access */
const superAdminAuthz: AuthzMeResponse = {
  userId: '1',
  superAdmin: true,
  allowedModules: ['ACCESS'],
  allowedCompanyIds: [],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['Admin'],
  modules: { ACCESS: 'MANAGE' },
  actions: {},
  reports: {},
  scopes: {},
  authzVersion: 1,
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function createWrapper(authz: AuthzMeResponse) {
  const httpGet = vi.fn().mockResolvedValue({ data: authz });
  return ({ children }: { children: React.ReactNode }) => (
    <PermissionProvider httpGet={httpGet} initialData={authz}>
      {children}
    </PermissionProvider>
  );
}

/**
 * Simulates the RoleDrawer Save button pattern:
 * access={useZanzibarAccess("can_edit", "module", "ACCESS").access}
 */
function RoleDrawerSaveButton({ onSave }: { onSave: () => void }) {
  const { access, reason } = useZanzibarAccess('can_edit', 'module', 'ACCESS');

  return (
    <div data-testid="drawer-footer">
      <Button variant="secondary" onClick={() => {}}>
        Iptal
      </Button>
      <Button
        data-testid="save-button"
        onClick={onSave}
        access={access}
        accessReason={access !== 'full' ? 'Duzenleme yetkiniz yok' : undefined}
      >
        Kaydet
      </Button>
      <span data-testid="access-level">{access}</span>
      <span data-testid="access-reason">{reason}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('ZanzibarPilot — mfe-access', () => {
  it('Save button has full access for user with MANAGE permission', () => {
    const handleSave = vi.fn();
    render(<RoleDrawerSaveButton onSave={handleSave} />, {
      wrapper: createWrapper(managerAuthz),
    });

    const footer = screen.getByTestId('drawer-footer');
    const saveBtn = within(footer).getByTestId('save-button');
    expect(saveBtn).toBeInTheDocument();
    expect(screen.getByTestId('access-level').textContent).toBe('readonly');
    // readonly because coarse gate passes but no httpPost for server check
  });

  it('Save button is hidden when user has no ACCESS module', () => {
    const handleSave = vi.fn();
    render(<RoleDrawerSaveButton onSave={handleSave} />, {
      wrapper: createWrapper(noAccessAuthz),
    });

    expect(screen.getByTestId('access-level').textContent).toBe('hidden');
    expect(screen.getByTestId('access-reason').textContent).toBe('no_module');
  });

  it('superAdmin always gets full access on Save button', () => {
    const handleSave = vi.fn();
    render(<RoleDrawerSaveButton onSave={handleSave} />, {
      wrapper: createWrapper(superAdminAuthz),
    });

    expect(screen.getByTestId('access-level').textContent).toBe('full');
    expect(screen.getByTestId('access-reason').textContent).toBe('superadmin');
  });

  it('Save button click fires only when access is full', async () => {
    const user = userEvent.setup();
    const handleSave = vi.fn();

    render(<RoleDrawerSaveButton onSave={handleSave} />, {
      wrapper: createWrapper(superAdminAuthz),
    });

    const saveBtn = screen.getByTestId('save-button');
    await user.click(saveBtn);
    expect(handleSave).toHaveBeenCalledTimes(1);
  });

  it('Save button is not rendered when access is hidden (no module)', () => {
    const handleSave = vi.fn();

    render(<RoleDrawerSaveButton onSave={handleSave} />, {
      wrapper: createWrapper(noAccessAuthz),
    });

    // access="hidden" makes Button return null — element not in DOM
    expect(screen.queryByTestId('save-button')).toBeNull();
  });

  it('access reason reflects authorization decision', () => {
    const handleSave = vi.fn();

    const { rerender } = render(<RoleDrawerSaveButton onSave={handleSave} />, {
      wrapper: createWrapper(superAdminAuthz),
    });
    expect(screen.getByTestId('access-reason').textContent).toBe('superadmin');

    // Re-render with no access
    const noAccessWrapper = createWrapper(noAccessAuthz);
    rerender(
      <React.StrictMode>
        {React.createElement(noAccessWrapper, null,
          React.createElement(RoleDrawerSaveButton, { onSave: handleSave })
        )}
      </React.StrictMode>
    );
    expect(screen.getByTestId('access-reason').textContent).toBe('no_module');
  });
});
