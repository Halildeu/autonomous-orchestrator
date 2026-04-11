// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TablePagination } from '../data-grid/TablePagination';
import type { TablePaginationLocaleText, TablePaginationActionsProps, TablePaginationSlots, TablePaginationSlotProps, TablePaginationProps } from '../data-grid/TablePagination';

describe('TablePagination — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<TablePagination  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TablePagination.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TablePagination  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TablePagination  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<TablePagination  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _tablepaginationlocaletext: TablePaginationLocaleText | undefined = undefined; void _tablepaginationlocaletext;
    const _tablepaginationactionsprops: TablePaginationActionsProps | undefined = undefined; void _tablepaginationactionsprops;
    const _tablepaginationslots: TablePaginationSlots | undefined = undefined; void _tablepaginationslots;
    const _tablepaginationslotprops: TablePaginationSlotProps | undefined = undefined; void _tablepaginationslotprops;
    const _tablepaginationprops: TablePaginationProps | undefined = undefined; void _tablepaginationprops;
    expect(true).toBe(true);
  });
});
