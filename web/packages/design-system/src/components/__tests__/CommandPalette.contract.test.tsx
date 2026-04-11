// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { CommandPalette } from '../command-palette/CommandPalette';
import type { CommandPaletteItem, CommandPaletteProps } from '../command-palette/CommandPalette';

describe('CommandPalette — contract', () => {
  const defaultProps = {
    open: true,
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<CommandPalette {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(CommandPalette.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<CommandPalette {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<CommandPalette {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<CommandPalette {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _commandpaletteitem: CommandPaletteItem | undefined = undefined; void _commandpaletteitem;
    const _commandpaletteprops: CommandPaletteProps | undefined = undefined; void _commandpaletteprops;
    expect(true).toBe(true);
  });
});
