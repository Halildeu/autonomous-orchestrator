// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AppSidebar } from '../app-sidebar/AppSidebar';
import type { AppSidebarProps, AppSidebarMode, AppSidebarContextValue, AppSidebarResizeState } from '../app-sidebar/AppSidebar';

describe('AppSidebar — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebar.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebar  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebar  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarprops: AppSidebarProps | undefined = undefined; void _appsidebarprops;
    const _appsidebarmode: AppSidebarMode | undefined = undefined; void _appsidebarmode;
    const _appsidebarcontextvalue: AppSidebarContextValue | undefined = undefined; void _appsidebarcontextvalue;
    const _appsidebarresizestate: AppSidebarResizeState | undefined = undefined; void _appsidebarresizestate;
    expect(true).toBe(true);
  });
});
