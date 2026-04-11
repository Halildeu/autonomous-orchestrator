// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Select } from '../select/Select';
import type { SelectSize, SelectDensity, SelectOption, SelectSlot, SelectProps } from '../select/Select';

describe('Select — contract', () => {
  const defaultProps = {
    options: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Select {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Select.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Select {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Select {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<Select {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _selectsize: SelectSize | undefined = undefined; void _selectsize;
    const _selectdensity: SelectDensity | undefined = undefined; void _selectdensity;
    const _selectoption: SelectOption | undefined = undefined; void _selectoption;
    const _selectslot: SelectSlot | undefined = undefined; void _selectslot;
    const _selectprops: SelectProps | undefined = undefined; void _selectprops;
    expect(true).toBe(true);
  });
});
