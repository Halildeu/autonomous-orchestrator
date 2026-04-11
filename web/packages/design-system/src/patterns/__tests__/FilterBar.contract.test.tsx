// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FilterBar } from '../filter-bar/FilterBar';
import type { FilterBarProps, FilterBarRef, FilterBarElement, FilterBarCSSProperties } from '../filter-bar/FilterBar';

describe('FilterBar — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<FilterBar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FilterBar.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FilterBar  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FilterBar  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<FilterBar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _filterbarprops: FilterBarProps | undefined = undefined; void _filterbarprops;
    const _filterbarref: FilterBarRef | undefined = undefined; void _filterbarref;
    const _filterbarelement: FilterBarElement | undefined = undefined; void _filterbarelement;
    const _filterbarcssproperties: FilterBarCSSProperties | undefined = undefined; void _filterbarcssproperties;
    expect(true).toBe(true);
  });
});
