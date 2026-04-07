import type { Page } from '@playwright/test';

export const JWT_HEADER = 'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0';
export const JWT_SIGNATURE = 'shell';
const AUTH_CHANNEL_NAME = 'shell-auth';
const SESSION_TTL_MS = 60 * 60 * 1000;
const DEFAULT_AUTH_MODE = 'none';
const AUTH_WAIT_TIMEOUT_MS = 60_000;

export interface TestTokenPayload {
  permissions: string[];
  sessionTimeoutMinutes?: number;
  [key: string]: unknown;
}

export interface TestUserProfile {
  id: string;
  fullName: string;
  email: string;
  permissions: string[];
  role: string;
}

export interface TestSession {
  token: string;
  user: TestUserProfile;
}

type TokenCache = {
  token: string;
  expiresAtMs: number;
};

let cachedToken: TokenCache | null = null;

const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  try {
    const parts = token.split('.');
    if (parts.length < 2) {
      return null;
    }
    const normalized = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + (4 - (normalized.length % 4 || 4)) % 4, '=');
    const decoded = Buffer.from(padded, 'base64').toString('utf8');
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
};

const extractJwtRoles = (claims: Record<string, unknown> | null): string[] => {
  if (!claims) {
    return [];
  }
  const realmAccess = claims.realm_access as { roles?: unknown } | undefined;
  const resourceAccess = claims.resource_access as Record<string, { roles?: unknown } | undefined> | undefined;
  const frontendRoles = resourceAccess?.frontend?.roles;
  const roles = [
    ...(Array.isArray(realmAccess?.roles) ? realmAccess.roles : []),
    ...(Array.isArray(frontendRoles) ? frontendRoles : []),
  ];
  return roles
    .map((value) => String(value ?? '').trim().toUpperCase())
    .filter(Boolean);
};

const buildInjectedUserProfile = (token: string, permissions: string[]): TestUserProfile => {
  const claims = decodeJwtPayload(token);
  const tokenRoles = extractJwtRoles(claims);
  const email =
    String(
      claims?.email ??
      claims?.preferred_username ??
      claims?.sub ??
      'runtime@test.local',
    ).trim() || 'runtime@test.local';
  const fullName =
    String(
      claims?.name ??
      claims?.given_name ??
      claims?.preferred_username ??
      email,
    ).trim() || email;
  const effectivePermissions = permissions.length > 0 ? permissions : tokenRoles;
  const effectiveRole = tokenRoles.includes('ADMIN') ? 'ADMIN' : (tokenRoles[0] ?? 'USER');

  return {
    id: String(claims?.sub ?? email),
    fullName,
    email,
    permissions: effectivePermissions,
    role: effectiveRole,
  };
};

const sanitizeBase64 = (value: string) =>
  value
    .replace(/=+$/, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');

export const buildTestToken = (permissions: string[] = []): TestSession => {
  const tokenPayload: TestTokenPayload = {
    permissions,
    sessionTimeoutMinutes: 60,
  };
  const encodedPayload = sanitizeBase64(Buffer.from(JSON.stringify(tokenPayload)).toString('base64'));

  const user: TestUserProfile = {
    id: 'e03-runtime-user',
    fullName: 'Runtime Test User',
    email: 'runtime@test.local',
    permissions,
    role: 'ADMIN',
  };

  return {
    token: `${JWT_HEADER}.${encodedPayload}.${JWT_SIGNATURE}`,
    user,
  };
};

const resolveAuthMode = () => (process.env.PW_AUTH_MODE ?? DEFAULT_AUTH_MODE).trim().toLowerCase();

const readInjectedToken = () => (process.env.PW_TEST_TOKEN ?? '').trim();
const shouldUseFakeAuth = () => (process.env.PW_FAKE_AUTH ?? '').trim() === '1';
const readFakeAuthPermissions = (fallback: string[]) => {
  const raw = (process.env.PW_FAKE_AUTH_PERMISSIONS ?? '').trim();
  if (!raw) return fallback;
  return raw
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
};
const installFakeAuthEnv = async (page: Page, permissions: string[]) => {
  const resolvedPermissions = readFakeAuthPermissions(permissions);
  await page.addInitScript(
    ({ nextPermissions }) => {
      const current = (window as Window & { __env__?: Record<string, string>; __ENV__?: Record<string, string> }).__env__ ?? {};
      const merged = {
        ...current,
        VITE_AUTH_MODE: 'permitAll',
        VITE_ENABLE_FAKE_AUTH: '1',
        VITE_FAKE_AUTH_PERMISSIONS: nextPermissions.join(','),
        VITE_FAKE_AUTH_EMAIL: 'runtime@test.local',
        VITE_FAKE_AUTH_NAME: 'Runtime Test User',
        VITE_FAKE_AUTH_DISPLAY: 'Runtime Test User',
        VITE_FAKE_AUTH_ROLE: 'ADMIN',
      };
      (window as Window & { __env__?: Record<string, string>; __ENV__?: Record<string, string> }).__env__ = merged;
      (window as Window & { __env__?: Record<string, string>; __ENV__?: Record<string, string> }).__ENV__ = merged;
    },
    { nextPermissions: resolvedPermissions },
  );
};

const hasTokenEndpointConfig = () => {
  const url = (process.env.KEYCLOAK_TOKEN_URL ?? '').trim();
  const clientId = (process.env.KEYCLOAK_CLIENT_ID ?? '').trim();
  const clientSecret = (process.env.KEYCLOAK_CLIENT_SECRET ?? '').trim();
  return Boolean(url && clientId && clientSecret);
};

const fetchClientCredentialsToken = async (): Promise<string> => {
  if (cachedToken && Date.now() + 30_000 < cachedToken.expiresAtMs) {
    return cachedToken.token;
  }

  const tokenUrl = (process.env.KEYCLOAK_TOKEN_URL ?? '').trim();
  const clientId = (process.env.KEYCLOAK_CLIENT_ID ?? '').trim();
  const clientSecret = (process.env.KEYCLOAK_CLIENT_SECRET ?? '').trim();
  const scope = (process.env.KEYCLOAK_SCOPE ?? 'openid').trim();

  if (!tokenUrl || !clientId || !clientSecret) {
    throw new Error('TOKEN_NOT_PROVIDED');
  }

  const body = new URLSearchParams();
  body.set('grant_type', 'client_credentials');
  body.set('client_id', clientId);
  body.set('client_secret', clientSecret);
  if (scope) body.set('scope', scope);

  const response = await fetch(tokenUrl, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // ignore
  }

  const accessToken = (payload as { access_token?: unknown } | null)?.access_token;
  if (!response.ok || typeof accessToken !== 'string' || !accessToken.trim()) {
    const status = response.status;
    const errorHint = (payload as { error?: unknown; error_description?: unknown } | null) ?? {};
    const err = String(errorHint.error ?? '').trim();
    const desc = String(errorHint.error_description ?? '').trim();
    const details = [err, desc].filter(Boolean).join(' ');
    throw new Error(details ? `TOKEN_ENDPOINT_FAILED (${status}): ${details}` : `TOKEN_ENDPOINT_FAILED (${status})`);
  }

  const expiresInRaw = (payload as { expires_in?: unknown } | null)?.expires_in;
  const expiresInSec = typeof expiresInRaw === 'number' ? expiresInRaw : Number(expiresInRaw ?? 0);
  const ttlMs = Number.isFinite(expiresInSec) && expiresInSec > 0 ? expiresInSec * 1000 : SESSION_TTL_MS;
  cachedToken = { token: accessToken, expiresAtMs: Date.now() + ttlMs };

  return accessToken;
};

export const buildAuthSession = async (permissions: string[] = []): Promise<TestSession> => {
  const authMode = resolveAuthMode();
  if (authMode !== 'token_injection') {
    return buildTestToken(permissions);
  }

  const injectedToken = readInjectedToken();
  const token = injectedToken || (hasTokenEndpointConfig() ? await fetchClientCredentialsToken() : '');
  if (!token) throw new Error('TOKEN_NOT_PROVIDED');

  return {
    token,
    user: buildInjectedUserProfile(token, permissions),
  };
};

export const applyAuthState = async (page: Page, session: TestSession, ttlMs: number = SESSION_TTL_MS) => {
  await page.evaluate(
    ([channelName, token, profile, ttl, eventName]) => {
      const payload = { token, profile, expiresAt: Date.now() + ttl };
      if (typeof window.BroadcastChannel === 'function') {
        const channel = new BroadcastChannel(channelName);
        channel.postMessage(payload);
      } else {
        window.dispatchEvent(new CustomEvent(eventName, { detail: payload }));
      }
    },
    [AUTH_CHANNEL_NAME, session.token, session.user, ttlMs, 'shell:set-auth-state'],
  );
};

const installSessionState = async (page: Page, session: TestSession, expiresAtMs: number) => {
  await page.evaluate(
    ({ token, user, nextExpiresAtMs }) => {
      try {
        window.localStorage.setItem('token', token);
        window.localStorage.setItem('user', JSON.stringify(user));
        window.localStorage.setItem('tokenExpiresAt', String(nextExpiresAtMs));
      } catch {
        // ignore
      }

      const store = (window as any).__shellStore;
      if (!store) {
        return;
      }

      store.dispatch({
        type: 'auth/setKeycloakSession',
        payload: {
          token,
          profile: user,
          expiresAt: nextExpiresAtMs,
        },
      });
      store.dispatch({ type: 'auth/setAuthInitialized', payload: true });
    },
    { token: session.token, user: session.user, nextExpiresAtMs: expiresAtMs },
  );
};

const waitForShellStore = async (page: Page) => {
  await page.waitForFunction(() => typeof (window as any).__shellStore !== 'undefined', { timeout: AUTH_WAIT_TIMEOUT_MS });
};

const waitForAuthState = async (page: Page) => {
  await page.waitForFunction(() => {
    const state = (window as any).__shellStore?.getState?.()?.auth;
    return Boolean(state?.initialized && state?.token);
  }, { timeout: AUTH_WAIT_TIMEOUT_MS });
};

export const authenticateAndNavigate = async (
  page: Page,
  baseURL: string | undefined,
  targetPath: string,
  permissions: string[],
) => {
  if (shouldUseFakeAuth()) {
    const root = baseURL ?? 'http://localhost:3000';
    await installFakeAuthEnv(page, permissions);
    await page.goto(`${root}${targetPath}`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => typeof (window as any).__shellStore !== 'undefined', { timeout: 30_000 });
    return { session: buildTestToken(readFakeAuthPermissions(permissions)), root };
  }
  const session = await buildAuthSession(permissions);
  const root = baseURL ?? 'http://localhost:3000';
  const expiresAt = Date.now() + SESSION_TTL_MS;
  await page.goto(`${root}/login`, { waitUntil: 'domcontentloaded' });
  await waitForShellStore(page);
  await installSessionState(page, session, expiresAt);
  await waitForAuthState(page);
  await applyAuthState(page, session);

  // Full navigation is more stable than pushState for remote-mounted routes.
  await page.goto(`${root}${targetPath}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction((nextPath) => window.location.pathname === nextPath, targetPath, { timeout: AUTH_WAIT_TIMEOUT_MS });
  await waitForShellStore(page);
  await installSessionState(page, session, expiresAt);
  await applyAuthState(page, session);
  await waitForAuthState(page);
  return { session, root };
};
