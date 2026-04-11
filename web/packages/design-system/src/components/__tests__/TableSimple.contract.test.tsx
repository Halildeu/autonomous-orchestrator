// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TableSimple } from '../table-simple/TableSimple';
import type { TableSimpleDensity, TableSimpleAlign, TableSimpleColumn, TableSimpleLocaleText, TableSimpleProps } from '../table-simple/TableSimple';

describe('TableSimple — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<TableSimple  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TableSimple.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TableSimple  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TableSimple  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _tablesimpledensity: TableSimpleDensity | undefined = undefined; void _tablesimpledensity;
    const _tablesimplealign: TableSimpleAlign | undefined = undefined; void _tablesimplealign;
    const _tablesimplecolumn: TableSimpleColumn | undefined = undefined; void _tablesimplecolumn;
    const _tablesimplelocaletext: TableSimpleLocaleText | undefined = undefined; void _tablesimplelocaletext;
    const _tablesimpleprops: TableSimpleProps | undefined = undefined; void _tablesimpleprops;
    expect(true).toBe(true);
  });
});
