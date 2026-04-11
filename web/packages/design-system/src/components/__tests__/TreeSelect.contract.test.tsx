// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TreeSelect } from '../tree-select/TreeSelect';
import type { TreeSelectNode, TreeSelectSize, TreeSelectProps } from '../tree-select/TreeSelect';

describe('TreeSelect — contract', () => {
  const defaultProps = {
    data: [],
  };

  it('renders without crash', () => {
    const { container } = render(<TreeSelect {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TreeSelect.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 14 optional)', () => {
    // All 14 optional props omitted — should not crash
    const { container } = render(<TreeSelect {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _treeselectnode: TreeSelectNode | undefined = undefined; void _treeselectnode;
    const _treeselectsize: TreeSelectSize | undefined = undefined; void _treeselectsize;
    const _treeselectprops: TreeSelectProps | undefined = undefined; void _treeselectprops;
    expect(true).toBe(true);
  });
});
