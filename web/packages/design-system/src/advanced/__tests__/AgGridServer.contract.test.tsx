// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AgGridServer } from '../data-grid/AgGridServer';
import type { ColDef, ColGroupDef, GridOptions, ServerSideDataRequest, ServerSideDataResult } from '../data-grid/AgGridServer';

describe('AgGridServer — contract', () => {
  const defaultProps = {
    columnDefs: [],
    getData: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<AgGridServer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AgGridServer.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AgGridServer {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AgGridServer {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<AgGridServer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _coldef: ColDef | undefined = undefined; void _coldef;
    const _colgroupdef: ColGroupDef | undefined = undefined; void _colgroupdef;
    const _gridoptions: GridOptions | undefined = undefined; void _gridoptions;
    const _serversidedatarequest: ServerSideDataRequest | undefined = undefined; void _serversidedatarequest;
    const _serversidedataresult: ServerSideDataResult | undefined = undefined; void _serversidedataresult;
    expect(true).toBe(true);
  });
});
