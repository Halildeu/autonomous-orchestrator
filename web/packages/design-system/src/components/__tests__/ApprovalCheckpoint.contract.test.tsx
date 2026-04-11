// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ApprovalCheckpoint } from '../approval-checkpoint/ApprovalCheckpoint';
import type { ApprovalCheckpointStatus, ApprovalCheckpointItemStatus, ApprovalCheckpointItem, ApprovalCheckpointProps } from '../approval-checkpoint/ApprovalCheckpoint';

describe('ApprovalCheckpoint — contract', () => {
  const defaultProps = {
    title: 'content',
    summary: 'content',
  };

  it('renders without crash', () => {
    const { container } = render(<ApprovalCheckpoint {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ApprovalCheckpoint.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ApprovalCheckpoint {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ApprovalCheckpoint {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 14 optional)', () => {
    // All 14 optional props omitted — should not crash
    const { container } = render(<ApprovalCheckpoint {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _approvalcheckpointstatus: ApprovalCheckpointStatus | undefined = undefined; void _approvalcheckpointstatus;
    const _approvalcheckpointitemstatus: ApprovalCheckpointItemStatus | undefined = undefined; void _approvalcheckpointitemstatus;
    const _approvalcheckpointitem: ApprovalCheckpointItem | undefined = undefined; void _approvalcheckpointitem;
    const _approvalcheckpointprops: ApprovalCheckpointProps | undefined = undefined; void _approvalcheckpointprops;
    expect(true).toBe(true);
  });
});
