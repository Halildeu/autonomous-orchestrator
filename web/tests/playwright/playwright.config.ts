import { defineConfig, devices } from '@playwright/test';

const executablePath = (process.env.PLAYWRIGHT_EXECUTABLE_PATH ?? '').trim();
const treatInsecureOriginAsSecure = (
  process.env.PLAYWRIGHT_TREAT_INSECURE_AS_SECURE_ORIGIN ?? ''
).trim();
const chromiumArgs = treatInsecureOriginAsSecure
  ? [`--unsafely-treat-insecure-origin-as-secure=${treatInsecureOriginAsSecure}`]
  : [];

export default defineConfig({
  testDir: __dirname,
  timeout: 60 * 1000,
  retries: 0,
  reporter: [['list']],
  fullyParallel: false,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    headless: true,
    viewport: { width: 1280, height: 800 },
    actionTimeout: 15 * 1000,
    navigationTimeout: 30 * 1000,
    ignoreHTTPSErrors: true,
    trace: 'on-first-retry',
    video: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...((executablePath || chromiumArgs.length > 0)
          ? {
              launchOptions: {
                ...(executablePath ? { executablePath } : {}),
                ...(chromiumArgs.length > 0 ? { args: chromiumArgs } : {}),
              },
            }
          : {}),
      },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
