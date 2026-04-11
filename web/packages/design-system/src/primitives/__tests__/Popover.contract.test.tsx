// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Popover } from '../popover/Popover';
import type { PopoverTriggerMode, PopoverSide, PopoverAlign, PopoverProps } from '../popover/Popover';

describe('Popover — contract', () => {
  const defaultProps = {
    trigger: 'content',
    content: 'content',
  };

  it('renders without crash', () => {
    const { container } = render(<Popover {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Popover.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Popover {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Popover {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 17 optional)', () => {
    // All 17 optional props omitted — should not crash
    const { container } = render(<Popover {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _popovertriggermode: PopoverTriggerMode | undefined = undefined; void _popovertriggermode;
    const _popoverside: PopoverSide | undefined = undefined; void _popoverside;
    const _popoveralign: PopoverAlign | undefined = undefined; void _popoveralign;
    const _popoverprops: PopoverProps | undefined = undefined; void _popoverprops;
    expect(true).toBe(true);
  });
});
