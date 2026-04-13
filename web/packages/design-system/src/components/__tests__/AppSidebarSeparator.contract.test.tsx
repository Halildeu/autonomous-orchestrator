// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';

vi.mock('../app-sidebar/useSidebar', () => ({
  useSidebar: () => ({
    mode: 'expanded', toggle: vi.fn(), expand: vi.fn(), collapse: vi.fn(),
    isCollapsed: false, resize: null, setWidth: vi.fn(), setIsResizing: vi.fn(),
  }),
  SidebarContext: { Provider: ({ children }: any) => children },
}));

import { AppSidebarSeparator } from '../app-sidebar/AppSidebarSeparator';
import type { AppSidebarSeparatorProps, AppSidebarSeparatorRef, AppSidebarSeparatorElement, AppSidebarSeparatorCSSProperties } from '../app-sidebar/AppSidebarSeparator';

describe('AppSidebarSeparator — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarSeparator  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarSeparator.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebarSeparator  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebarSeparator  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarseparatorprops: AppSidebarSeparatorProps | undefined = undefined; void _appsidebarseparatorprops;
    const _appsidebarseparatorref: AppSidebarSeparatorRef | undefined = undefined; void _appsidebarseparatorref;
    const _appsidebarseparatorelement: AppSidebarSeparatorElement | undefined = undefined; void _appsidebarseparatorelement;
    const _appsidebarseparatorcssproperties: AppSidebarSeparatorCSSProperties | undefined = undefined; void _appsidebarseparatorcssproperties;
    expect(true).toBe(true);
  });
});
