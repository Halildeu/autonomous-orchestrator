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

import { AppSidebarFooterStatus } from '../app-sidebar/AppSidebarFooterStatus';
import type { AppSidebarFooterStatusProps } from '../app-sidebar/AppSidebarFooterStatus';

describe('AppSidebarFooterStatus — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<AppSidebarFooterStatus  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarFooterStatus.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<AppSidebarFooterStatus  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarfooterstatusprops: AppSidebarFooterStatusProps | undefined = undefined; void _appsidebarfooterstatusprops;
    expect(true).toBe(true);
  });
});
