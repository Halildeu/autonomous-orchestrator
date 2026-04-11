// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AppSidebarFooterAction } from '../app-sidebar/AppSidebarFooterAction';
import type { AppSidebarFooterActionProps } from '../app-sidebar/AppSidebarFooterAction';

describe('AppSidebarFooterAction — contract', () => {
  const defaultProps = {
    icon: 'content',
    label: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<AppSidebarFooterAction {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AppSidebarFooterAction.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<AppSidebarFooterAction {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _appsidebarfooteractionprops: AppSidebarFooterActionProps | undefined = undefined; void _appsidebarfooteractionprops;
    expect(true).toBe(true);
  });
});
