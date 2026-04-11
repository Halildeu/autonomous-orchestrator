// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AppSidebarNavItem } from '../app-sidebar/AppSidebarNavItem';
import type { AppSidebarNavItemProps, AppSidebarNavItemRef, AppSidebarNavItemElement, AppSidebarNavItemCSSProperties } from '../app-sidebar/AppSidebarNavItem';

describe('AppSidebarNavItem — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarNavItem  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarNavItem.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebarNavItem  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebarNavItem  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarnavitemprops: AppSidebarNavItemProps | undefined = undefined; void _appsidebarnavitemprops;
    const _appsidebarnavitemref: AppSidebarNavItemRef | undefined = undefined; void _appsidebarnavitemref;
    const _appsidebarnavitemelement: AppSidebarNavItemElement | undefined = undefined; void _appsidebarnavitemelement;
    const _appsidebarnavitemcssproperties: AppSidebarNavItemCSSProperties | undefined = undefined; void _appsidebarnavitemcssproperties;
    expect(true).toBe(true);
  });
});
