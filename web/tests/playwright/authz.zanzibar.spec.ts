import { test, expect, type Page } from '@playwright/test';

type AuthzSnapshot = {
  userId?: string;
  permissions?: string[];
  allowedModules?: string[];
  modules?: Record<string, string>;
  superAdmin?: boolean;
};

const TEST_EMAIL = (process.env.PW_REAL_USER_EMAIL ?? 'user3@example.com').trim();
const TEST_PASSWORD = (process.env.PW_REAL_USER_PASSWORD ?? '').trim();

const isVisible = async (page: Page, selectors: string[]): Promise<boolean> => {
  for (const selector of selectors) {
    if (await page.locator(selector).first().isVisible().catch(() => false)) {
      return true;
    }
  }
  return false;
};

const fillFirst = async (page: Page, selectors: string[], value: string) => {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (await locator.isVisible().catch(() => false)) {
      await locator.fill(value);
      return;
    }
  }
  throw new Error(`Beklenen input bulunamadı: ${selectors.join(', ')}`);
};

const clickFirst = async (page: Page, selectors: string[]) => {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (await locator.isVisible().catch(() => false)) {
      await locator.click();
      return;
    }
  }
  throw new Error(`Beklenen buton bulunamadı: ${selectors.join(', ')}`);
};

const performBrowserLogin = async (page: Page, root: string, email: string, password: string) => {
  await page.context().clearCookies();
  await page.goto(`${root}/login?redirect=${encodeURIComponent('/access/roles')}`, {
    waitUntil: 'domcontentloaded',
  });

  const appLoginButtonSelectors = [
    '[data-testid="corporate-login-button"]',
    'button:has-text("Güvenli Kurumsal Giriş")',
    'button:has-text("Kurumsal Giriş")',
    'button:has-text("Sign In")',
  ];
  if (await isVisible(page, appLoginButtonSelectors)) {
    await clickFirst(page, appLoginButtonSelectors);
  }

  const keycloakUserSelectors = ['#username', 'input[name="username"]', 'input[type="email"]'];
  const keycloakPassSelectors = ['#password', 'input[name="password"]', 'input[type="password"]'];
  const keycloakSubmitSelectors = ['#kc-login', 'button[type="submit"]', 'input[type="submit"]'];

  const keycloakVisible = await page
    .waitForFunction(
      ({ userSelectors }) => {
        return userSelectors.some((selector) => !!document.querySelector(selector));
      },
      { userSelectors: keycloakUserSelectors },
      { timeout: 20_000 },
    )
    .then(() => true)
    .catch(() => false);

  if (keycloakVisible) {
    await fillFirst(page, keycloakUserSelectors, email);
    await fillFirst(page, keycloakPassSelectors, password);
    await clickFirst(page, keycloakSubmitSelectors);
  }

  await page.waitForURL(
    (url) => {
      const href = url.toString();
      return !href.includes('/realms/') && (href.includes('/access/roles') || href.includes('/login') || href.includes('/unauthorized'));
    },
    { timeout: 60_000 },
  );
};

const readBrowserToken = async (page: Page): Promise<string> => {
  await page.waitForFunction(() => {
    const token = window.localStorage.getItem('token');
    const stateToken = (window as any).__shellStore?.getState?.()?.auth?.token;
    return Boolean(token || stateToken);
  }, { timeout: 30_000 });

  return page.evaluate(() => {
    return (
      window.localStorage.getItem('token') ??
      (window as any).__shellStore?.getState?.()?.auth?.token ??
      ''
    );
  });
};

const deriveAllowedModules = (authz: AuthzSnapshot): string[] => {
  const modules = new Set<string>();

  const addModule = (raw: string | undefined) => {
    const value = String(raw ?? '').trim().toUpperCase();
    if (!value) {
      return;
    }

    switch (value) {
      case 'ACCESS':
      case 'ACCESS-READ':
      case 'VIEW_ACCESS':
        modules.add('ACCESS');
        return;
      case 'AUDIT':
      case 'AUDIT-READ':
      case 'VIEW_AUDIT':
        modules.add('AUDIT');
        return;
      case 'REPORT':
      case 'REPORT_VIEW':
      case 'VIEW_REPORTS':
      case 'REPORT_EXPORT':
      case 'REPORT_MANAGE':
        modules.add('REPORT');
        return;
      case 'THEME':
      case 'THEME_ADMIN':
        modules.add('THEME');
        return;
      case 'USER_MANAGEMENT':
      case 'USER-READ':
      case 'VIEW_USERS':
      case 'MANAGE_USERS':
        modules.add('USER_MANAGEMENT');
        return;
      default:
        modules.add(value);
    }
  };

  (authz.allowedModules ?? []).forEach(addModule);
  Object.keys(authz.modules ?? {}).forEach(addModule);
  (authz.permissions ?? []).forEach(addModule);

  return Array.from(modules);
};

const fetchAuthzSnapshot = async (root: string, token: string): Promise<AuthzSnapshot> => {
  const candidates = ['/api/v1/authz/me', '/v1/authz/me'];
  let lastStatus = 0;

  for (const path of candidates) {
    const response = await fetch(`${root}${path}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
      },
    });

    lastStatus = response.status;
    if (!response.ok) {
      continue;
    }

    const contentType = response.headers.get('content-type') ?? '';
    if (!contentType.toLowerCase().startsWith('application/json')) {
      continue;
    }

    return (await response.json().catch(() => ({}))) as AuthzSnapshot;
  }

  expect(false, `authz snapshot endpoint'i bulunamadı. son HTTP durum: ${lastStatus}`).toBeTruthy();
  return {} as AuthzSnapshot;
};

test.describe('Zanzibar authz live smoke', () => {
  test('restricted user yalnız yetkili modülleri görür ve theme alanında unauthorized alır', async ({ page, baseURL }) => {
    test.skip(!TEST_PASSWORD, 'PW_REAL_USER_PASSWORD tanımlı değil.');

    const root = baseURL ?? 'http://localhost:3000';
    await performBrowserLogin(page, root, TEST_EMAIL, TEST_PASSWORD);
    const token = await readBrowserToken(page);
    const authz = await fetchAuthzSnapshot(root, token);
    const allowedModules = deriveAllowedModules(authz);

    expect(authz.superAdmin).toBeFalsy();
    if (authz.userId !== undefined && authz.userId !== null) {
      expect(String(authz.userId).trim().length > 0, 'userId boş dönmemeli').toBeTruthy();
    }
    expect(allowedModules).toEqual(expect.arrayContaining(['ACCESS', 'AUDIT', 'REPORT']));
    expect(allowedModules).not.toContain('THEME');

    await page.goto(`${root}/access/roles`, { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/access\/roles/, { timeout: 30_000 });
    await expect(page.locator('.ag-root')).toBeVisible({ timeout: 30_000 });

    await page.goto(`${root}/admin/themes`, { waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(/\/unauthorized/, { timeout: 30_000 });
    await expect(page.getByRole('heading', { name: /Erişim Yetkiniz Bulunmuyor|You do not have access/i })).toBeVisible();
  });
});
