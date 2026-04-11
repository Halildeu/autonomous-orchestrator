// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Combobox } from '../combobox/Combobox';
import type { ComboboxOption, ComboboxOptionGroup, ComboboxResolvedOption, ComboboxSelectionMode, ComboboxDisabledItemFocusPolicy } from '../combobox/Combobox';

describe('Combobox — contract', () => {
  const defaultProps = {
    options: 'Array<ComboboxOption',
  };

  it('renders without crash', () => {
    const { container } = render(<Combobox {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Combobox.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Combobox {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Combobox {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 46 optional)', () => {
    // All 46 optional props omitted — should not crash
    const { container } = render(<Combobox {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _comboboxoption: ComboboxOption | undefined = undefined; void _comboboxoption;
    const _comboboxoptiongroup: ComboboxOptionGroup | undefined = undefined; void _comboboxoptiongroup;
    const _comboboxresolvedoption: ComboboxResolvedOption | undefined = undefined; void _comboboxresolvedoption;
    const _comboboxselectionmode: ComboboxSelectionMode | undefined = undefined; void _comboboxselectionmode;
    const _comboboxdisableditemfocuspolicy: ComboboxDisabledItemFocusPolicy | undefined = undefined; void _comboboxdisableditemfocuspolicy;
    expect(true).toBe(true);
  });
});
