// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Tree } from '../tree/Tree';
import type { TreeDensity, TreeTone, TreeNode, TreeLocaleText, TreeProps } from '../tree/Tree';

describe('Tree — contract', () => {
  const defaultProps = {
    nodes: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Tree {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Tree.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Tree {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Tree {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 12 optional)', () => {
    // All 12 optional props omitted — should not crash
    const { container } = render(<Tree {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _treedensity: TreeDensity | undefined = undefined; void _treedensity;
    const _treetone: TreeTone | undefined = undefined; void _treetone;
    const _treenode: TreeNode | undefined = undefined; void _treenode;
    const _treelocaletext: TreeLocaleText | undefined = undefined; void _treelocaletext;
    const _treeprops: TreeProps | undefined = undefined; void _treeprops;
    expect(true).toBe(true);
  });
});
