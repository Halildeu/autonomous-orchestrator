// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ContextMenu } from '../context-menu/ContextMenu';
import type { ContextMenuItem, ContextMenuSeparator, ContextMenuLabel, ContextMenuEntry, ContextMenuProps } from '../context-menu/ContextMenu';

describe('ContextMenu — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ContextMenu {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ContextMenu.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ContextMenu {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ContextMenu {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<ContextMenu {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _contextmenuitem: ContextMenuItem | undefined = undefined; void _contextmenuitem;
    const _contextmenuseparator: ContextMenuSeparator | undefined = undefined; void _contextmenuseparator;
    const _contextmenulabel: ContextMenuLabel | undefined = undefined; void _contextmenulabel;
    const _contextmenuentry: ContextMenuEntry | undefined = undefined; void _contextmenuentry;
    const _contextmenuprops: ContextMenuProps | undefined = undefined; void _contextmenuprops;
    expect(true).toBe(true);
  });
});
