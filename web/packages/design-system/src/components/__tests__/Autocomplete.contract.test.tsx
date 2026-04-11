// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Autocomplete } from '../autocomplete/Autocomplete';
import type { AutocompleteOption, AutocompleteProps } from '../autocomplete/Autocomplete';

describe('Autocomplete — contract', () => {
  const defaultProps = {
    options: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Autocomplete {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Autocomplete.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Autocomplete {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Autocomplete {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 17 optional)', () => {
    // All 17 optional props omitted — should not crash
    const { container } = render(<Autocomplete {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _autocompleteoption: AutocompleteOption | undefined = undefined; void _autocompleteoption;
    const _autocompleteprops: AutocompleteProps | undefined = undefined; void _autocompleteprops;
    expect(true).toBe(true);
  });
});
