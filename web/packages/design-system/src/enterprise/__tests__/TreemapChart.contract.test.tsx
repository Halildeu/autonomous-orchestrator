// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TreemapChart } from '../TreemapChart';
import type { TreemapItem, TreemapChartProps } from '../TreemapChart';

describe('TreemapChart — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<TreemapChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TreemapChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TreemapChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TreemapChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<TreemapChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _treemapitem: TreemapItem | undefined = undefined; void _treemapitem;
    const _treemapchartprops: TreemapChartProps | undefined = undefined; void _treemapchartprops;
    expect(true).toBe(true);
  });
});
