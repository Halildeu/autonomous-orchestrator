import { expect, test, type Page } from '@playwright/test';

const FATAL_RUNTIME_PATTERNS = [
  /Shared module ['"][^'"]+['"] must be provided by host/i,
  /\[Module Federation\].*must be provided by host/i,
  /Cannot read properties of null \(reading ['"]useMemo['"]\)/i,
  /ScriptExternalLoadError/i,
  /Loading script failed/i,
];

const LOGIN_RENDER_TIMEOUT_MS = 15_000;

type LoginUiState = {
  bodyPreview: string;
  hasHeading: boolean;
  hasIndicator: boolean;
  url: string;
};

const readLoginUiState = async (page: Page): Promise<LoginUiState> => {
  const bodyText = ((await page.locator('body').textContent().catch(() => '')) ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 240);

  return {
    bodyPreview: bodyText,
    hasHeading: await page
      .getByRole('heading', { name: /Giriş Yap|Login|Sign In/i })
      .isVisible()
      .catch(() => false),
    hasIndicator: await page
      .locator('[data-testid="corporate-login-button"], [data-testid="corporate-login-pending"]')
      .first()
      .isVisible()
      .catch(() => false),
    url: page.url(),
  };
};

test.describe('Single-domain preauth runtime smoke', () => {
  test('login route renders without early federation/runtime crash', async ({ page, baseURL }) => {
    const failures: string[] = [];

    const captureFailure = (source: string, message: string) => {
      if (FATAL_RUNTIME_PATTERNS.some((pattern) => pattern.test(message))) {
        failures.push(`${source}: ${message}`);
      }
    };

    page.on('console', (msg) => {
      const text = msg.text();
      if (
        msg.type() === 'error' ||
        text.includes('[Module Federation]') ||
        text.includes('Shared module')
      ) {
        captureFailure(`console.${msg.type()}`, text);
      }
    });

    page.on('pageerror', (error) => {
      captureFailure('pageerror', `${error.message}\n${error.stack ?? ''}`);
    });

    await page.addInitScript(() => {
      window.addEventListener('error', (event) => {
        const error = event.error as Error | undefined;
        console.error(
          `[single-domain-runtime-smoke] window-error ${event.message} ${error?.stack ?? ''}`.trim(),
        );
      });

      window.addEventListener('unhandledrejection', (event) => {
        const reason = event.reason as { message?: string; stack?: string } | undefined;
        console.error(
          `[single-domain-runtime-smoke] window-rejection ${reason?.message ?? String(event.reason ?? '')} ${reason?.stack ?? ''}`.trim(),
        );
      });
    });

    const root = baseURL ?? 'http://127.0.0.1:4173';
    await page.goto(`${root}/login?redirect=${encodeURIComponent('/access/roles')}`, {
      waitUntil: 'domcontentloaded',
    });

    await expect(page.locator('body')).toBeVisible();
    const deadline = Date.now() + LOGIN_RENDER_TIMEOUT_MS;
    let uiState = await readLoginUiState(page);

    while (Date.now() < deadline) {
      if (failures.length > 0 || (uiState.hasHeading && uiState.hasIndicator)) {
        break;
      }
      await page.waitForTimeout(250);
      uiState = await readLoginUiState(page);
    }

    if (failures.length > 0) {
      throw new Error(
        `Login route yüklenirken fatal federation/runtime hatası görüldü:\n${failures.join('\n')}\nurl=${uiState.url}\nbody=${uiState.bodyPreview}`,
      );
    }

    expect(
      uiState.hasHeading,
      `Login heading görünmedi. url=${uiState.url} body=${uiState.bodyPreview}`,
    ).toBeTruthy();
    expect(
      uiState.hasIndicator,
      `Login butonu/pending göstergesi görünmedi. url=${uiState.url} body=${uiState.bodyPreview}`,
    ).toBeTruthy();

    await page.waitForTimeout(2_500);

    expect(
      failures,
      `Login route yüklenirken fatal federation/runtime hatası görüldü:\n${failures.join('\n')}`,
    ).toHaveLength(0);

    const loginPath = new URL(page.url()).pathname;
    expect(loginPath).toBe('/login');
  });
});
