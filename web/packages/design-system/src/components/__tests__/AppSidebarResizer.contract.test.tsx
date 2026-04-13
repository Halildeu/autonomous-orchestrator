// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';

vi.mock('../app-sidebar/useSidebar', () => ({
  useSidebar: () => ({
    mode: 'expanded', toggle: vi.fn(), expand: vi.fn(), collapse: vi.fn(),
    isCollapsed: false,
    resize: { width: 260, minWidth: 200, maxWidth: 500, isResizing: false },
    setWidth: vi.fn(), setIsResizing: vi.fn(),
  }),
  SidebarContext: { Provider: ({ children }: any) => children },
}));

import { AppSidebarResizer } from '../app-sidebar/AppSidebarResizer';
import type { AppSidebarResizerProps, AppSidebarResizerRef, AppSidebarResizerElement, AppSidebarResizerCSSProperties } from '../app-sidebar/AppSidebarResizer';

describe('AppSidebarResizer — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarResizer  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarResizer.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebarResizer  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebarResizer  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarresizerprops: AppSidebarResizerProps | undefined = undefined; void _appsidebarresizerprops;
    const _appsidebarresizerref: AppSidebarResizerRef | undefined = undefined; void _appsidebarresizerref;
    const _appsidebarresizerelement: AppSidebarResizerElement | undefined = undefined; void _appsidebarresizerelement;
    const _appsidebarresizercssproperties: AppSidebarResizerCSSProperties | undefined = undefined; void _appsidebarresizercssproperties;
    expect(true).toBe(true);
  });
});
