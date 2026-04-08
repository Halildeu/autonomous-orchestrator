// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { UserMenuDropdown } from '../UserMenuDropdown';

/* ---- mocks ---- */

const navigateMock = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock('../../../store/store.hooks', () => ({
  useAppSelector: (sel: (s: Record<string, unknown>) => unknown) =>
    sel({
      auth: {
        user: { fullName: 'Halil K.', email: 'halil@test.com', role: 'Admin' },
      },
    }),
  useAppDispatch: () => vi.fn(),
}));

vi.mock('@mfe/auth', () => ({
  usePermissions: () => ({
    hasModule: () => true,
    isSuperAdmin: () => false,
  }),
}));

vi.mock('../../../../features/auth/lib/permissions.constants', () => ({
  MODULE_KEYS: { AUDIT: 'AUDIT', THEME: 'THEME' },
}));

vi.mock('../../../../features/auth/model/auth.slice', () => ({
  logout: vi.fn(() => ({ type: 'auth/logout' })),
}));

vi.mock('../../../auth/auth-config', () => ({
  buildAppRedirectUri: (uri: string) => uri,
  isPermitAllMode: () => false,
}));

vi.mock('../../../auth/keycloakClient', () => ({
  default: { logout: vi.fn() },
}));

vi.mock('../../../i18n', () => ({
  useShellCommonI18n: () => ({
    t: (key: string) => key,
    locale: 'tr',
  }),
}));

vi.mock('@mfe/design-system', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@mfe/design-system');
  return {
    ...actual,
    Avatar: ({ initials }: { initials: string }) => <span data-testid="avatar">{initials}</span>,
    Dropdown: ({ children, items }: { children: React.ReactNode; items: unknown[] }) => (
      <div data-testid="dropdown">
        {children}
        <span data-testid="dropdown-count">{items.length}</span>
      </div>
    ),
    Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  };
});

/* ---- tests ---- */

describe('UserMenuDropdown', () => {
  it('renders user initials in avatar', () => {
    render(<UserMenuDropdown />);
    expect(screen.getByTestId('avatar')).toHaveTextContent('HK');
  });

  it('renders dropdown trigger with aria-label', () => {
    render(<UserMenuDropdown />);
    expect(screen.getByLabelText('shell.userMenu.title')).toBeInTheDocument();
  });

  it('passes menu items to dropdown', () => {
    render(<UserMenuDropdown />);
    const count = Number(screen.getByTestId('dropdown-count').textContent);
    // user-info + separator + last-login + separator + audit + settings + profile + separator + logout
    expect(count).toBeGreaterThanOrEqual(7);
  });
});
