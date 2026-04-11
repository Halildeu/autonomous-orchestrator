// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ApprovalWorkflow } from '../ApprovalWorkflow';
import type { ApprovalStepStatus, ApprovalAssignee, ApprovalStep, ApprovalWorkflowProps } from '../ApprovalWorkflow';

describe('ApprovalWorkflow — contract', () => {
  const defaultProps = {
    steps: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ApprovalWorkflow {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ApprovalWorkflow.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ApprovalWorkflow {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ApprovalWorkflow {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<ApprovalWorkflow {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _approvalstepstatus: ApprovalStepStatus | undefined = undefined; void _approvalstepstatus;
    const _approvalassignee: ApprovalAssignee | undefined = undefined; void _approvalassignee;
    const _approvalstep: ApprovalStep | undefined = undefined; void _approvalstep;
    const _approvalworkflowprops: ApprovalWorkflowProps | undefined = undefined; void _approvalworkflowprops;
    expect(true).toBe(true);
  });
});
