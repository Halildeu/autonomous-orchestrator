// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PivotTable } from '../PivotTable';
import type { PivotValueConfig, PivotCellClickEvent, PivotTableProps } from '../PivotTable';

describe('PivotTable — contract', () => {
  const defaultProps = {
    data: [],
    rows: [],
    columns: [],
    values: [],
  };

  it('renders without crash', () => {
    const { container } = render(<PivotTable {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(PivotTable.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<PivotTable {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<PivotTable {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (4 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<PivotTable {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _pivotvalueconfig: PivotValueConfig | undefined = undefined; void _pivotvalueconfig;
    const _pivotcellclickevent: PivotCellClickEvent | undefined = undefined; void _pivotcellclickevent;
    const _pivottableprops: PivotTableProps | undefined = undefined; void _pivottableprops;
    expect(true).toBe(true);
  });
});
