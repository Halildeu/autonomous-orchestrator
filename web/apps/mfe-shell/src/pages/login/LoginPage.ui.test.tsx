// @vitest-environment jsdom
import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

const authModeMock = { permitAll: false };
const authStateMock = { token: null as string | null, initialized: true };
const { startKeycloakLoginMock, resolveKeycloakLoginUrlMock } = vi.hoisted(() => ({
  startKeycloakLoginMock: vi.fn().mockResolvedValue(undefined),
  resolveKeycloakLoginUrlMock: vi.fn().mockResolvedValue('https://ai.acik.com/realms/serban/protocol/openid-connect/auth'),
}));

vi.mock('../../app/auth/keycloakClient', () => ({
  default: {
    login: vi.fn().mockResolvedValue(undefined),
  },
  startKeycloakLogin: startKeycloakLoginMock,
  resolveKeycloakLoginUrl: resolveKeycloakLoginUrlMock,
}));

vi.mock('@mfe/design-system', () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock('../../app/i18n', () => ({
  useShellCommonI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../app/auth/auth-config', () => ({
  isPermitAllMode: () => authModeMock.permitAll,
  buildAppRedirectUri: (value?: string) => `http://localhost:3000${value ?? '/'}`,
}));

vi.mock('../../app/store/store.hooks', () => ({
  useAppSelector: (selector: (state: { auth: typeof authStateMock }) => unknown) =>
    selector({ auth: authStateMock }),
}));

import { startKeycloakLogin } from '../../app/auth/keycloakClient';
import LoginPage from './LoginPage.ui';

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authModeMock.permitAll = false;
    authStateMock.token = null;
    authStateMock.initialized = true;
    resolveKeycloakLoginUrlMock.mockResolvedValue('https://ai.acik.com/realms/serban/protocol/openid-connect/auth');
  });

  afterEach(() => {
    cleanup();
  });

  it('renders corporate login button', () => {
    render(
      <MemoryRouter initialEntries={['/login']} future={routerFuture}>
        <LoginPage />
      </MemoryRouter>,
    );

    const button = screen.getByTestId('corporate-login-button');
    expect(button).toBeInTheDocument();
    expect(button).toHaveTextContent('Güvenli Kurumsal Giriş');
  });

  it('hazirlanan login href bilgisini butona baglar', async () => {
    render(
      <MemoryRouter initialEntries={['/login?redirect=/access/roles']} future={routerFuture}>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId('corporate-login-button')).toHaveAttribute(
        'href',
        'https://ai.acik.com/realms/serban/protocol/openid-connect/auth',
      ),
    );
  });

  it('login href hazirlanamazsa startKeycloakLogin fallbackini kullanir', async () => {
    resolveKeycloakLoginUrlMock.mockResolvedValueOnce(null);

    render(
      <MemoryRouter initialEntries={['/login?redirect=/access/roles']} future={routerFuture}>
        <LoginPage />
      </MemoryRouter>,
    );

    const button = await screen.findByTestId('corporate-login-button');
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => expect(startKeycloakLogin).toHaveBeenCalledTimes(1));
    expect(startKeycloakLogin).toHaveBeenCalledWith({
      redirectUri: 'http://localhost:3000/login?redirect=%2Faccess%2Froles',
    });
  });

  it('keycloak init tamamlanmadan login butonunu devre disi birakir', () => {
    authStateMock.initialized = false;

    render(
      <MemoryRouter initialEntries={['/login?redirect=/access/roles']} future={routerFuture}>
        <LoginPage />
      </MemoryRouter>,
    );

    const button = screen.getByTestId('corporate-login-button');
    expect(button).toBeDisabled();
    expect(screen.getByTestId('corporate-login-pending')).toBeInTheDocument();

    fireEvent.click(button);
    expect(startKeycloakLogin).not.toHaveBeenCalled();
  });

  it('shows permitAll mode with Devam Et button', () => {
    authModeMock.permitAll = true;
    render(
      <MemoryRouter initialEntries={['/login']} future={routerFuture}>
        <LoginPage />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Geliştirme modunda/)).toBeInTheDocument();
    expect(screen.getByText('Devam Et')).toBeInTheDocument();
    expect(screen.queryByTestId('corporate-login-button')).toBeNull();
  });
});
