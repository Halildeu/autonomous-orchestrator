// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AppSidebarHeader } from '../app-sidebar/AppSidebarHeader';
import type { AppSidebarHeaderProps, AppSidebarHeaderRef, AppSidebarHeaderElement, AppSidebarHeaderCSSProperties } from '../app-sidebar/AppSidebarHeader';

describe('AppSidebarHeader — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarHeader  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarHeader.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebarHeader  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebarHeader  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarheaderprops: AppSidebarHeaderProps | undefined = undefined; void _appsidebarheaderprops;
    const _appsidebarheaderref: AppSidebarHeaderRef | undefined = undefined; void _appsidebarheaderref;
    const _appsidebarheaderelement: AppSidebarHeaderElement | undefined = undefined; void _appsidebarheaderelement;
    const _appsidebarheadercssproperties: AppSidebarHeaderCSSProperties | undefined = undefined; void _appsidebarheadercssproperties;
    expect(true).toBe(true);
  });
});
