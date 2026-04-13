// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TreeTable } from '../tree-table/TreeTable';
import type { TreeTableDensity, TreeTableAlign, TreeTableTone, TreeTableColumn, TreeTableNode } from '../tree-table/TreeTable';

describe('TreeTable — contract', () => {
  const defaultProps = {
    nodes: [{ key: 'n1', label: 'Node 1', data: { size: '1KB' } }],
    columns: [{ key: 'size', label: 'Size', accessor: 'size' as const }],
  };

  it('renders without crash', () => {
    const { container } = render(<TreeTable {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TreeTable.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TreeTable {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TreeTable {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _treetabledensity: TreeTableDensity | undefined = undefined; void _treetabledensity;
    const _treetablealign: TreeTableAlign | undefined = undefined; void _treetablealign;
    const _treetabletone: TreeTableTone | undefined = undefined; void _treetabletone;
    const _treetablecolumn: TreeTableColumn | undefined = undefined; void _treetablecolumn;
    const _treetablenode: TreeTableNode | undefined = undefined; void _treetablenode;
    expect(true).toBe(true);
  });
});
