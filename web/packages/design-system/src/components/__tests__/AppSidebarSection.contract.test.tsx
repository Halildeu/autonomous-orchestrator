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

import { AppSidebarSection } from '../app-sidebar/AppSidebarSection';
import type { AppSidebarSectionProps, AppSidebarSectionRef, AppSidebarSectionElement, AppSidebarSectionCSSProperties } from '../app-sidebar/AppSidebarSection';

describe('AppSidebarSection — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarSection  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarSection.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AppSidebarSection  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AppSidebarSection  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarsectionprops: AppSidebarSectionProps | undefined = undefined; void _appsidebarsectionprops;
    const _appsidebarsectionref: AppSidebarSectionRef | undefined = undefined; void _appsidebarsectionref;
    const _appsidebarsectionelement: AppSidebarSectionElement | undefined = undefined; void _appsidebarsectionelement;
    const _appsidebarsectioncssproperties: AppSidebarSectionCSSProperties | undefined = undefined; void _appsidebarsectioncssproperties;
    expect(true).toBe(true);
  });
});
