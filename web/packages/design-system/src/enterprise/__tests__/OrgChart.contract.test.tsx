// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { OrgChart } from '../OrgChart';
import type { OrgChartNode, OrgChartProps } from '../OrgChart';

describe('OrgChart — contract', () => {
  const defaultProps = {
    data: { id: 'root', label: 'CEO', children: [] },
  };

  it('renders without crash', () => {
    const { container } = render(<OrgChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(OrgChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<OrgChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<OrgChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<OrgChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _orgchartnode: OrgChartNode | undefined = undefined; void _orgchartnode;
    const _orgchartprops: OrgChartProps | undefined = undefined; void _orgchartprops;
    expect(true).toBe(true);
  });
});
