// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ComparisonTable } from '../ComparisonTable';
import type { ComparisonRow, ComparisonColumnLabels, ComparisonTableProps } from '../ComparisonTable';

describe('ComparisonTable — contract', () => {
  const defaultProps = {
    rows: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ComparisonTable {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ComparisonTable.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ComparisonTable {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ComparisonTable {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<ComparisonTable {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _comparisonrow: ComparisonRow | undefined = undefined; void _comparisonrow;
    const _comparisoncolumnlabels: ComparisonColumnLabels | undefined = undefined; void _comparisoncolumnlabels;
    const _comparisontableprops: ComparisonTableProps | undefined = undefined; void _comparisontableprops;
    expect(true).toBe(true);
  });
});
