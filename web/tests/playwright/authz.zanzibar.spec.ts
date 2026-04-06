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

const waitForFirstVisible = async (
  page: Page,
  selectors: string[],
  timeoutMs = 15_000,
) => {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    for (const selector of selectors) {
      const locator = page.locator(selector).first();
      if (await locator.isVisible().catch(() => false)) {
        return locator;
      }
    }

    await page.waitForTimeout(250);
  }

  return null;
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

const summarizeUrl = (value: string): string => {
  try {
    const parsed = new URL(value);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return value;
  }
};

const performBrowserLogin = async (page: Page, root: string, email: string, password: string) => {
  await page.addInitScript(() => {
    window.addEventListener('error', (event) => {
      const error = event.error as Error | undefined;
      const payload = {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        stack: error?.stack ?? '',
      };
      console.log(`[authz-window-error] ${JSON.stringify(payload)}`);
    });

    window.addEventListener('unhandledrejection', (event) => {
      const reason = event.reason as { message?: string; stack?: string } | undefined;
      const payload = {
        message: reason?.message ?? String(event.reason ?? ''),
        stack: reason?.stack ?? '',
      };
      console.log(`[authz-window-rejection] ${JSON.stringify(payload)}`);
    });
  });

  page.on('console', (msg) => {
    const text = msg.text();
    if (/keycloak|login|auth/i.test(text)) {
      console.log(`[authz-smoke] console.${msg.type()}=${text}`);
    }
    if (text.startsWith('[authz-window-error]') || text.startsWith('[authz-window-rejection]')) {
      console.log(`[authz-smoke] console.${msg.type()}=${text}`);
    }
  });
  page.on('pageerror', (error) => {
    console.log(`[authz-smoke] pageerror=${error.message}`);
    if (error.stack) {
      console.log(`[authz-smoke] pageerror.stack=${error.stack}`);
    }
  });

  await page.context().clearCookies();
  await page.goto(`${root}/login?redirect=${encodeURIComponent('/access/roles')}`, {
    waitUntil: 'domcontentloaded',
  });
  const initialUrl = page.url();
  const runtimeEnv = await page.evaluate(() => {
    const env = ((window as any).__env__ ?? (window as any).__ENV__ ?? {}) as Record<string, string>;
    return {
      authMode: env.VITE_AUTH_MODE ?? env.AUTH_MODE ?? '',
      keycloakUrl: env.VITE_KEYCLOAK_URL ?? env.KEYCLOAK_URL ?? '',
      keycloakRealm: env.VITE_KEYCLOAK_REALM ?? env.KEYCLOAK_REALM ?? '',
      keycloakClientId: env.VITE_KEYCLOAK_CLIENT_ID ?? env.KEYCLOAK_CLIENT_ID ?? '',
      isSecureContext: window.isSecureContext,
      hasCryptoSubtle: Boolean(window.crypto?.subtle),
    };
  });
  console.log(
    `[authz-smoke] runtime_env authMode=${runtimeEnv.authMode} keycloakUrl=${runtimeEnv.keycloakUrl} realm=${runtimeEnv.keycloakRealm} clientId=${runtimeEnv.keycloakClientId} secureContext=${runtimeEnv.isSecureContext} subtle=${runtimeEnv.hasCryptoSubtle}`,
  );

  const appLoginButtonSelectors = [
    '[data-testid="corporate-login-button"]',
    'button:has-text("Güvenli Kurumsal Giriş")',
    'button:has-text("Kurumsal Giriş")',
    'button:has-text("Sign In")',
  ];
  const loginButton = await waitForFirstVisible(page, appLoginButtonSelectors, 15_000);
  if (loginButton) {
    let loginHref: string | null = null;
    await expect(loginButton).toBeEnabled({ timeout: 30_000 });
    loginHref = await loginButton.getAttribute('href').catch(() => null);
    console.log(
      `[authz-smoke] login_button enabled=${await loginButton.isEnabled().catch(() => false)} text=${await loginButton.textContent().catch(() => '')}`,
    );
    if (loginHref) {
      console.log(`[authz-smoke] login_href=${summarizeUrl(loginHref)}`);
    }

    const beforeClickUrl = page.url();
    await loginButton.click();
    await page.waitForURL((url) => url.toString() !== beforeClickUrl || url.toString().includes('/realms/'), {
      timeout: 20_000,
    }).catch(() => undefined);

    if (page.url() === beforeClickUrl && loginHref) {
      console.log(`[authz-smoke] click navigation başlamadı; direct goto fallback=${summarizeUrl(loginHref)}`);
      await page.goto(loginHref, { waitUntil: 'domcontentloaded' }).catch(() => undefined);
    }
  } else {
    console.log('[authz-smoke] login_button görünmedi; login page render gecikmesi veya runtime sorunu olabilir');
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

  if (page.url() === initialUrl && !keycloakVisible) {
    throw new Error(`Login butonu sonrası yönlendirme başlamadı. url=${page.url()}`);
  }

  if (keycloakVisible) {
    await fillFirst(page, keycloakUserSelectors, email);
    await fillFirst(page, keycloakPassSelectors, password);
    await clickFirst(page, keycloakSubmitSelectors);
  }

  await page.waitForURL((url) => !url.toString().includes('/realms/'), { timeout: 60_000 });
  await page.waitForLoadState('domcontentloaded');
  console.log(`[authz-smoke] landing_url=${page.url()}`);
  console.log(`[authz-smoke] landing_title=${await page.title().catch(() => '-')}`);
  console.log(
    `[authz-smoke] landing_body=${((await page.locator('body').textContent().catch(() => '')) ?? '').replace(/\s+/g, ' ').slice(0, 240)}`,
  );

  await page.waitForFunction(() => {
    return Boolean(window.localStorage.getItem('token'));
  }, undefined, { timeout: 60_000 }).catch(async (error) => {
    const diagnostic = await page.evaluate(() => ({
      href: window.location.href,
      readyState: document.readyState,
      hasRoot: Boolean(document.querySelector('#root')),
      bodyClass: document.body?.className ?? '',
      hasLocalToken: Boolean(window.localStorage.getItem('token')),
    }));
    throw new Error(
      `browser token beklenirken timeout. href=${diagnostic.href} readyState=${diagnostic.readyState} hasRoot=${diagnostic.hasRoot} bodyClass=${diagnostic.bodyClass} hasLocalToken=${diagnostic.hasLocalToken} cause=${String(error)}`,
    );
  });
};

const readBrowserToken = async (page: Page): Promise<string> => {
  try {
    await page.waitForFunction(() => {
      return Boolean(window.localStorage.getItem('token'));
    }, undefined, { timeout: 60_000 });
  } catch (error) {
    const diagnostic = await page.evaluate(() => {
      return {
        href: window.location.href,
        hasLocalToken: Boolean(window.localStorage.getItem('token')),
      };
    });
    throw new Error(
      `Browser token beklenirken timeout. href=${diagnostic.href} localToken=${diagnostic.hasLocalToken} cause=${String(error)}`,
    );
  }

  return page.evaluate(() => {
    return window.localStorage.getItem('token') ?? '';
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

const fetchAuthzSnapshot = async (page: Page, root: string, token: string): Promise<AuthzSnapshot> => {
  const candidates = ['/api/v1/authz/me', '/v1/authz/me'];
  const result = await page.evaluate(
    async ({ currentRoot, currentToken, paths }) => {
      let lastStatus = 0;

      for (const path of paths) {
        const response = await fetch(`${currentRoot}${path}`, {
          headers: {
            Authorization: `Bearer ${currentToken}`,
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

        return {
          ok: true,
          lastStatus,
          snapshot: await response.json().catch(() => ({})),
        };
      }

      return {
        ok: false,
        lastStatus,
        snapshot: {},
      };
    },
    { currentRoot: root, currentToken: token, paths: candidates },
  );

  expect(result.ok, `authz snapshot endpoint'i bulunamadı. son HTTP durum: ${result.lastStatus}`).toBeTruthy();
  if (result.ok) {
    return result.snapshot as AuthzSnapshot;
  }
  return {} as AuthzSnapshot;
};

test.describe('Zanzibar authz live smoke', () => {
  test('restricted user yalnız yetkili modülleri görür ve theme alanında unauthorized alır', async ({ page, baseURL }) => {
    test.skip(!TEST_PASSWORD, 'PW_REAL_USER_PASSWORD tanımlı değil.');

    const root = baseURL ?? 'http://localhost:3000';
    await performBrowserLogin(page, root, TEST_EMAIL, TEST_PASSWORD);
    const token = await readBrowserToken(page);
    const authz = await fetchAuthzSnapshot(page, root, token);
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
