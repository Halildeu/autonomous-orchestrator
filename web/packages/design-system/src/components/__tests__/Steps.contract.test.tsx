// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Steps } from '../steps/Steps';
import type { StepsSize, StepsDirection, StepStatus, StepItem, StepsProps } from '../steps/Steps';

describe('Steps — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Steps {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Steps.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Steps {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Steps {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<Steps {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _stepssize: StepsSize | undefined = undefined; void _stepssize;
    const _stepsdirection: StepsDirection | undefined = undefined; void _stepsdirection;
    const _stepstatus: StepStatus | undefined = undefined; void _stepstatus;
    const _stepitem: StepItem | undefined = undefined; void _stepitem;
    const _stepsprops: StepsProps | undefined = undefined; void _stepsprops;
    expect(true).toBe(true);
  });
});
