import { test, expect } from '@playwright/test';

/* ------------------------------------------------------------------ */
/*  Visual Regression — RTL (Right-to-Left)                            */
/*                                                                     */
/*  Captures RTL rendering of core interactive components.             */
/*  Each test navigates to the story with direction=rtl global and     */
/*  compares against committed RTL baselines.                          */
/*                                                                     */
/*  PURPOSE: Detect layout/alignment regressions in RTL mode for       */
/*  components used in production. Covers text alignment, icon         */
/*  positioning, dropdown direction, and spacing mirroring.            */
/* ------------------------------------------------------------------ */

const STORYBOOK_BASE = 'http://localhost:6006';

/** Navigate to a story in RTL mode */
async function openStoryRTL(page: import('@playwright/test').Page, storyId: string) {
  await page.goto(
    `${STORYBOOK_BASE}/iframe.html?id=${storyId}&viewMode=story&globals=direction:rtl`,
    { waitUntil: 'networkidle' },
  );
  await page.waitForTimeout(500);
}

/* ---- Core Form Inputs ---- */

test.describe('RTL — Form Inputs', () => {
  test('Input', async ({ page }) => {
    await openStoryRTL(page, 'primitives-input--default');
    await expect(page).toHaveScreenshot('rtl-input-default.png');
  });

  test('Select', async ({ page }) => {
    await openStoryRTL(page, 'primitives-select--default');
    await expect(page).toHaveScreenshot('rtl-select-default.png');
  });

  test('SearchInput', async ({ page }) => {
    await openStoryRTL(page, 'components-search-input--default');
    await expect(page).toHaveScreenshot('rtl-search-input-default.png');
  });
});

/* ---- Navigation ---- */

test.describe('RTL — Navigation', () => {
  test('Tabs', async ({ page }) => {
    await openStoryRTL(page, 'components-tabs--default');
    await expect(page).toHaveScreenshot('rtl-tabs-default.png');
  });

  test('MenuBar', async ({ page }) => {
    await openStoryRTL(page, 'components-menu-bar--default');
    await expect(page).toHaveScreenshot('rtl-menubar-default.png');
  });

  test('Pagination', async ({ page }) => {
    await openStoryRTL(page, 'components-pagination--default');
    await expect(page).toHaveScreenshot('rtl-pagination-default.png');
  });

  test('Breadcrumb', async ({ page }) => {
    await openStoryRTL(page, 'components-breadcrumb--default');
    await expect(page).toHaveScreenshot('rtl-breadcrumb-default.png');
  });
});

/* ---- Patterns ---- */

test.describe('RTL — Patterns', () => {
  test('FilterBar', async ({ page }) => {
    await openStoryRTL(page, 'patterns-filter-bar--default');
    await expect(page).toHaveScreenshot('rtl-filterbar-default.png');
  });

  test('DetailDrawer', async ({ page }) => {
    await openStoryRTL(page, 'patterns-detail-drawer--default');
    await expect(page).toHaveScreenshot('rtl-detaildrawer-default.png');
  });

  test('Accordion', async ({ page }) => {
    await openStoryRTL(page, 'components-accordion--default');
    await expect(page).toHaveScreenshot('rtl-accordion-default.png');
  });
});
