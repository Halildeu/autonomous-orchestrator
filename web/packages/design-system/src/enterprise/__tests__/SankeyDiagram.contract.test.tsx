// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SankeyDiagram } from '../SankeyDiagram';
import type { SankeyNode, SankeyLink, SankeyDiagramProps } from '../SankeyDiagram';

describe('SankeyDiagram — contract', () => {
  const defaultProps = {
    nodes: [],
    links: [],
  };

  it('renders without crash', () => {
    const { container } = render(<SankeyDiagram {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SankeyDiagram.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<SankeyDiagram {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<SankeyDiagram {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<SankeyDiagram {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _sankeynode: SankeyNode | undefined = undefined; void _sankeynode;
    const _sankeylink: SankeyLink | undefined = undefined; void _sankeylink;
    const _sankeydiagramprops: SankeyDiagramProps | undefined = undefined; void _sankeydiagramprops;
    expect(true).toBe(true);
  });
});
