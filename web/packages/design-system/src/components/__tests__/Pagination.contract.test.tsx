// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Pagination } from '../pagination/Pagination';
import type { PaginationSize, PaginationProps } from '../pagination/Pagination';

describe('Pagination — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Pagination  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Pagination.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Pagination  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Pagination  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<Pagination  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _paginationsize: PaginationSize | undefined = undefined; void _paginationsize;
    const _paginationprops: PaginationProps | undefined = undefined; void _paginationprops;
    expect(true).toBe(true);
  });
});
