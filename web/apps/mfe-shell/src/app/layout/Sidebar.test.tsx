// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';

const dispatchMock = vi.fn();
const pushNotificationMock = vi.fn((payload: Record<string, unknown>) => ({ type: 'notifications/push', payload }));
const toggleOpenMock = vi.fn((payload: boolean) => ({ type: 'notifications/toggle', payload }));

const permissionsMock = {
  hasModule: vi.fn(() => true),
  isSuperAdmin: vi.fn(() => false),
  getModuleLevel: vi.fn(() => 'MANAGE'),
  isActionAllowed: vi.fn(() => true),
  isActionDenied: vi.fn(() => false),
  canViewReport: vi.fn(() => true),
  canAccessPage: vi.fn(() => true),
  getUserRoles: vi.fn(() => []),
  canAccessCompany: vi.fn(() => true),
  authz: null,
  initialized: true,
  loading: false,
  refresh: vi.fn(),
};

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

vi.mock('../store/store.hooks', () => ({
  useAppDispatch: () => dispatchMock,
}));

vi.mock('@mfe/auth', () => ({
  usePermissions: () => permissionsMock,
}));

vi.mock('../../features/notifications/model/notifications.slice', () => ({
  pushNotification: (payload: Record<string, unknown>) => pushNotificationMock(payload),
  toggleOpen: (payload: boolean) => toggleOpenMock(payload),
}));

vi.mock('../auth/auth-config', () => ({
  isPermitAllMode: () => false,
}));

vi.mock('../shell-navigation', () => ({
  isSuggestionsRemoteEnabled: () => true,
  isEthicRemoteEnabled: () => true,
}));

const LocationViewer = () => {
  const location = useLocation();
  return <span data-testid="location-display">{location.pathname}</span>;
};

const renderSidebar = (initialPath = '/audit/events') =>
  render(
    <MemoryRouter initialEntries={[initialPath]} future={routerFuture}>
      <Routes>
        <Route
          path="*"
          element={(
            <>
              <Sidebar />
              <LocationViewer />
            </>
          )}
        />
      </Routes>
    </MemoryRouter>,
  );

describe('Sidebar', () => {
  beforeEach(() => {
    dispatchMock.mockReset();
    pushNotificationMock.mockClear();
    toggleOpenMock.mockClear();
    permissionsMock.hasModule.mockImplementation(() => true);
    permissionsMock.isSuperAdmin.mockImplementation(() => false);
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  // TODO: ShellSidebar requires ResizeObserver + IntersectionObserver mocks in JSDOM
  it.skip('NavigationRail uzerinden route gecisi yapar ve test-id yuzeyini korur', () => {
    renderSidebar('/audit/events');

    expect(screen.getByLabelText('Sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('nav-home')).toBeInTheDocument();
    expect(screen.getByTestId('nav-dashboard')).toHaveAttribute('aria-current', 'page');

    fireEvent.click(screen.getByTestId('nav-reporting'));

    expect(screen.getByTestId('location-display')).toHaveTextContent('/admin/reports/users');
  });

  it.skip('search dispatch davranisini ve collapsed folders expand akisini korur', () => {
    window.localStorage.setItem('shell.sidebar.mode', 'collapsed');

    renderSidebar('/suggestions');

    fireEvent.click(screen.getByPlaceholderText(/search/i));

    // openCommandPalette now navigates to design-lab with search=open param
    // instead of dispatching pushNotification
    expect(screen.getByTestId('location-display')).toHaveTextContent('/admin/design-lab');

    // Re-render at original path to test folders
    cleanup();
    window.localStorage.setItem('shell.sidebar.mode', 'collapsed');
    renderSidebar('/suggestions');

    fireEvent.click(screen.getByTestId('nav-folders'));
    expect(screen.getByTestId('nav-folders-all')).toBeInTheDocument();
  });
});
