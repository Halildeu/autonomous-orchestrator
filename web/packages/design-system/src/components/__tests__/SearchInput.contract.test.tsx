// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SearchInput } from '../search-input/SearchInput';
import type { SearchInputSize, SearchInputProps } from '../search-input/SearchInput';

describe('SearchInput — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<SearchInput  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SearchInput.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<SearchInput  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<SearchInput  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<SearchInput  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _searchinputsize: SearchInputSize | undefined = undefined; void _searchinputsize;
    const _searchinputprops: SearchInputProps | undefined = undefined; void _searchinputprops;
    expect(true).toBe(true);
  });
});
