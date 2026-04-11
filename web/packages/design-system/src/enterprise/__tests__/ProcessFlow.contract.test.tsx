// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ProcessFlow } from '../ProcessFlow';
import type { ProcessNodeType, ProcessNodeStatus, ProcessNode, ProcessEdge, ProcessFlowProps } from '../ProcessFlow';

describe('ProcessFlow — contract', () => {
  const defaultProps = {
    nodes: [],
    edges: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ProcessFlow {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ProcessFlow.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ProcessFlow {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ProcessFlow {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<ProcessFlow {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _processnodetype: ProcessNodeType | undefined = undefined; void _processnodetype;
    const _processnodestatus: ProcessNodeStatus | undefined = undefined; void _processnodestatus;
    const _processnode: ProcessNode | undefined = undefined; void _processnode;
    const _processedge: ProcessEdge | undefined = undefined; void _processedge;
    const _processflowprops: ProcessFlowProps | undefined = undefined; void _processflowprops;
    expect(true).toBe(true);
  });
});
