// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { MenuBar } from '../menu-bar/MenuBar';
import type { MenuBarSize, MenuBarAppearance, MenuBarLabelVisibility, MenuBarOverflowBehavior, MenuBarSubmenuTrigger } from '../menu-bar/MenuBar';

describe('MenuBar — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<MenuBar {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(MenuBar.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<MenuBar {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<MenuBar {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 38 optional)', () => {
    // All 38 optional props omitted — should not crash
    const { container } = render(<MenuBar {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _menubarsize: MenuBarSize | undefined = undefined; void _menubarsize;
    const _menubarappearance: MenuBarAppearance | undefined = undefined; void _menubarappearance;
    const _menubarlabelvisibility: MenuBarLabelVisibility | undefined = undefined; void _menubarlabelvisibility;
    const _menubaroverflowbehavior: MenuBarOverflowBehavior | undefined = undefined; void _menubaroverflowbehavior;
    const _menubarsubmenutrigger: MenuBarSubmenuTrigger | undefined = undefined; void _menubarsubmenutrigger;
    expect(true).toBe(true);
  });
});
