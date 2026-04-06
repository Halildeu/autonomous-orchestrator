import { test, expect } from '@playwright/test';
import { authenticateAndNavigate } from './utils/auth';

type AuthzSnapshot = {
  userId?: string;
  permissions?: string[];
  allowedModules?: string[];
  superAdmin?: boolean;
};

type ParsedTokenEndpoint = {
  baseUrl?: string;
  realm?: string;
};

const parseKeycloakTokenUrl = (rawUrl: string): ParsedTokenEndpoint => {
  if (!rawUrl) {
    return {};
  }

  try {
    const url = new URL(rawUrl);
    const match = url.pathname.match(/^(.*)\/realms\/([^/]+)\/protocol\/openid-connect\/token$/);

    if (!match) {
      return {};
    }

    const prefix = match[1] ?? '';
    const realm = match[2]?.trim();
    const baseUrl = `${url.origin}${prefix}`.replace(/\/$/, '');

    return {
      baseUrl: baseUrl || url.origin,
      realm,
    };
  } catch {
    return {};
  }
};

const derivedKeycloak = parseKeycloakTokenUrl((process.env.KEYCLOAK_TOKEN_URL ?? '').trim());
const KEYCLOAK_URL = (process.env.PW_KEYCLOAK_URL ?? derivedKeycloak.baseUrl ?? 'http://localhost:8081').trim();
const KEYCLOAK_REALM = (process.env.PW_KEYCLOAK_REALM ?? derivedKeycloak.realm ?? 'serban').trim();
const KEYCLOAK_CLIENT_ID = (process.env.PW_KEYCLOAK_CLIENT_ID ?? process.env.KEYCLOAK_CLIENT_ID ?? 'frontend').trim();
const KEYCLOAK_CLIENT_SECRET = (process.env.PW_KEYCLOAK_CLIENT_SECRET ?? process.env.KEYCLOAK_CLIENT_SECRET ?? '').trim();
const KEYCLOAK_SCOPE = (process.env.PW_KEYCLOAK_SCOPE ?? process.env.KEYCLOAK_SCOPE ?? 'openid').trim();
const TEST_EMAIL = (process.env.PW_REAL_USER_EMAIL ?? 'user3@example.com').trim();
const TEST_PASSWORD = (process.env.PW_REAL_USER_PASSWORD ?? '').trim();

const issuePasswordGrantToken = async (email: string, password: string): Promise<string> => {
  const body = new URLSearchParams();
  body.set('grant_type', 'password');
  body.set('client_id', KEYCLOAK_CLIENT_ID);
  body.set('username', email);
  body.set('password', password);
  if (KEYCLOAK_CLIENT_SECRET) {
    body.set('client_secret', KEYCLOAK_CLIENT_SECRET);
  }
  if (KEYCLOAK_SCOPE) {
    body.set('scope', KEYCLOAK_SCOPE);
  }

  const response = await fetch(
    `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    },
  );

  const payload = await response.json().catch(() => ({}));
  const token = typeof payload?.access_token === 'string' ? payload.access_token.trim() : '';

  expect(response.ok, `Keycloak token endpoint başarısız oldu: ${response.status}`).toBeTruthy();
  expect(token.length > 0, 'Restricted-user token alınamadı').toBeTruthy();

  return token;
};

const fetchAuthzSnapshot = async (root: string, token: string): Promise<AuthzSnapshot> => {
  const response = await fetch(`${root}/api/v1/authz/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const payload = (await response.json().catch(() => ({}))) as AuthzSnapshot;
  expect(response.ok, `/api/v1/authz/me beklenen gibi dönmedi: ${response.status}`).toBeTruthy();
  return payload;
};

test.describe('Zanzibar authz live smoke', () => {
  test('restricted user yalnız yetkili modülleri görür ve theme alanında unauthorized alır', async ({ page, baseURL }) => {
    test.skip(!TEST_PASSWORD, 'PW_REAL_USER_PASSWORD tanımlı değil.');

    const root = baseURL ?? 'http://localhost:3000';
    const token = await issuePasswordGrantToken(TEST_EMAIL, TEST_PASSWORD);
    const authz = await fetchAuthzSnapshot(root, token);
    const allowedModules = Array.isArray(authz.allowedModules)
      ? authz.allowedModules
      : (Array.isArray(authz.permissions) ? authz.permissions : []);

    expect(authz.superAdmin).toBeFalsy();
    expect(authz.userId).toBeTruthy();
    expect(allowedModules).toEqual(expect.arrayContaining(['ACCESS', 'AUDIT', 'REPORT']));
    expect(allowedModules).not.toContain('THEME');

    const previousToken = process.env.PW_TEST_TOKEN;
    process.env.PW_TEST_TOKEN = token;

    try {
      await authenticateAndNavigate(page, baseURL, '/access/roles', allowedModules);
      await expect(page).toHaveURL(/\/access\/roles/);
      await expect(page.locator('.ag-root')).toBeVisible({ timeout: 30_000 });

      await page.goto(`${root}/admin/themes`, { waitUntil: 'domcontentloaded' });
      await expect(page).toHaveURL(/\/unauthorized/, { timeout: 30_000 });
      await expect(page.getByRole('heading', { name: /Erişim Yetkiniz Bulunmuyor|You do not have access/i })).toBeVisible();
    } finally {
      if (typeof previousToken === 'string') {
        process.env.PW_TEST_TOKEN = previousToken;
      } else {
        delete process.env.PW_TEST_TOKEN;
      }
    }
  });
});
