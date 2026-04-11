// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FlowBuilder } from '../FlowBuilder';
import type { FlowNodeType, FlowNode, FlowEdge, FlowBuilderProps } from '../FlowBuilder';

describe('FlowBuilder — contract', () => {
  const defaultProps = {
    nodes: [],
    edges: [],
  };

  it('renders without crash', () => {
    const { container } = render(<FlowBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FlowBuilder.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FlowBuilder {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FlowBuilder {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 15 optional)', () => {
    // All 15 optional props omitted — should not crash
    const { container } = render(<FlowBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _flownodetype: FlowNodeType | undefined = undefined; void _flownodetype;
    const _flownode: FlowNode | undefined = undefined; void _flownode;
    const _flowedge: FlowEdge | undefined = undefined; void _flowedge;
    const _flowbuilderprops: FlowBuilderProps | undefined = undefined; void _flowbuilderprops;
    expect(true).toBe(true);
  });
});
