// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Drawer } from '../drawer/Drawer';
import type { DrawerPlacement, DrawerSize, DrawerProps } from '../drawer/Drawer';

describe('Drawer — contract', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
  };

  it('renders without crash', () => {
    // Drawer portals to document.body, so container.firstElementChild is null.
    // Check that the dialog role element appears in the document instead.
    render(<Drawer {...defaultProps} />);
    expect(document.querySelector('[role="dialog"]')).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Drawer.displayName).toBeTruthy();
  });

  it('renders with only required props (3 required, 9 optional)', () => {
    render(<Drawer {...defaultProps} />);
    expect(document.querySelector('[role="dialog"]')).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _drawerplacement: DrawerPlacement | undefined = undefined; void _drawerplacement;
    const _drawersize: DrawerSize | undefined = undefined; void _drawersize;
    const _drawerprops: DrawerProps | undefined = undefined; void _drawerprops;
    expect(true).toBe(true);
  });
});
