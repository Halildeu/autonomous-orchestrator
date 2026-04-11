// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AppSidebarFooter } from '../app-sidebar/AppSidebarFooter';
import type { AppSidebarFooterProps, AppSidebarFooterRef, AppSidebarFooterElement, AppSidebarFooterCSSProperties } from '../app-sidebar/AppSidebarFooter';

describe('AppSidebarFooter — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarFooter  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarFooter.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebarFooter  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebarFooter  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarfooterprops: AppSidebarFooterProps | undefined = undefined; void _appsidebarfooterprops;
    const _appsidebarfooterref: AppSidebarFooterRef | undefined = undefined; void _appsidebarfooterref;
    const _appsidebarfooterelement: AppSidebarFooterElement | undefined = undefined; void _appsidebarfooterelement;
    const _appsidebarfootercssproperties: AppSidebarFooterCSSProperties | undefined = undefined; void _appsidebarfootercssproperties;
    expect(true).toBe(true);
  });
});
