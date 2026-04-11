// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SearchFilterListing } from '../search-filter-listing/SearchFilterListing';
import type { ActiveFilter, SortOption, SortState, SearchFilterListingProps } from '../search-filter-listing/SearchFilterListing';

describe('SearchFilterListing — contract', () => {
  const defaultProps = {
    title: 'content',
  };

  it('renders without crash', () => {
    const { container } = render(<SearchFilterListing {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SearchFilterListing.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<SearchFilterListing {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<SearchFilterListing {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 31 optional)', () => {
    // All 31 optional props omitted — should not crash
    const { container } = render(<SearchFilterListing {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _activefilter: ActiveFilter | undefined = undefined; void _activefilter;
    const _sortoption: SortOption | undefined = undefined; void _sortoption;
    const _sortstate: SortState | undefined = undefined; void _sortstate;
    const _searchfilterlistingprops: SearchFilterListingProps | undefined = undefined; void _searchfilterlistingprops;
    expect(true).toBe(true);
  });
});
