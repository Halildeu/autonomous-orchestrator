// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { cleanup, render, screen } from '@testing-library/react';
import { ProtectedRoute } from './ProtectedRoute';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

const authState = {
  auth: {
    token: null as string | null,
    user: { email: 'admin@example.com' },
    initialized: true,
  },
};

const permissionsMock = {
  hasModule: () => true,
  isSuperAdmin: () => false,
};

const authModeMock = {
  permitAll: false,
};

vi.mock('../store/store.hooks', () => ({
  useAppSelector: (selector: any) => selector(authState),
}));

vi.mock('../auth/auth-config', () => ({
  isPermitAllMode: () => authModeMock.permitAll,
}));

vi.mock('@mfe/auth', () => ({
  usePermissions: () => permissionsMock,
}));

const LocationViewer = ({ label }: { label: string }) => {
  const location = useLocation();
  return (
    <div>
      <span>{label}</span>
      <span data-testid="location-display">{`${location.pathname}${location.search}`}</span>
      <span data-testid="location-state">{String((location.state as any)?.reason ?? 'none')}</span>
    </div>
  );
};

const renderWithRouter = () =>
  render(
    <MemoryRouter initialEntries={['/admin/users']} future={routerFuture}>
      <Routes>
        <Route
          path="/admin/users"
          element={(
            <ProtectedRoute requiredPermissions={['VIEW_USERS']}>
              <div>Protected Content</div>
            </ProtectedRoute>
          )}
        />
        <Route path="/login" element={<LocationViewer label="Login Page" />} />
        <Route path="/unauthorized" element={<LocationViewer label="Unauthorized Page" />} />
      </Routes>
    </MemoryRouter>,
  );

describe('ProtectedRoute', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    authState.auth.token = null;
    permissionsMock.hasModule = () => true;
    permissionsMock.isSuperAdmin = () => false;
    authState.auth.initialized = true;
    authModeMock.permitAll = false;
  });

  it('redirects anonymous user to login with redirect param', () => {
    renderWithRouter();
    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.getByTestId('location-display')).toHaveTextContent('/login?redirect=%2Fadmin%2Fusers');
  });

  it('permitAll bootstrap tamamlanmadan içerik render etmez', () => {
    authModeMock.permitAll = true;
    authState.auth.initialized = false;

    const { container } = renderWithRouter();

    expect(container).toBeEmptyDOMElement();
  });

  it('navigates authenticated but unauthorized user to /unauthorized', () => {
    authState.auth.token = 'valid-token';
    permissionsMock.hasModule = () => false;

    renderWithRouter();
    expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
  });

  it('renders children when authenticated and authorized', () => {
    authState.auth.token = 'valid-token';
    permissionsMock.hasModule = () => true;

    renderWithRouter();
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('permitAll modunda bootstrap sonrası token olmasa da children render eder', () => {
    authModeMock.permitAll = true;
    authState.auth.token = null;
    authState.auth.initialized = true;

    renderWithRouter();
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });
});
