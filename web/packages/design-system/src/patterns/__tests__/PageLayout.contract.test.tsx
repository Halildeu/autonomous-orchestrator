// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PageLayout } from '../page-layout/PageLayout';
import type { PageBreadcrumbItem, PageLayoutRouteInput, PageLayoutClasses, PageLayoutProps, PageLayoutPresetOptions } from '../page-layout/PageLayout';

describe('PageLayout — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<PageLayout  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(PageLayout.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<PageLayout  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<PageLayout  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 24 optional)', () => {
    // All 24 optional props omitted — should not crash
    const { container } = render(<PageLayout  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _pagebreadcrumbitem: PageBreadcrumbItem | undefined = undefined; void _pagebreadcrumbitem;
    const _pagelayoutrouteinput: PageLayoutRouteInput | undefined = undefined; void _pagelayoutrouteinput;
    const _pagelayoutclasses: PageLayoutClasses | undefined = undefined; void _pagelayoutclasses;
    const _pagelayoutprops: PageLayoutProps | undefined = undefined; void _pagelayoutprops;
    const _pagelayoutpresetoptions: PageLayoutPresetOptions | undefined = undefined; void _pagelayoutpresetoptions;
    expect(true).toBe(true);
  });
});
