// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ValueStream } from '../ValueStream';
import type { StepCategory, TimeUnit, ValueStreamStep, ValueStreamWait, ValueStreamProps } from '../ValueStream';

describe('ValueStream — contract', () => {
  const defaultProps = {
    steps: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ValueStream {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ValueStream.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ValueStream {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ValueStream {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<ValueStream {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _stepcategory: StepCategory | undefined = undefined; void _stepcategory;
    const _timeunit: TimeUnit | undefined = undefined; void _timeunit;
    const _valuestreamstep: ValueStreamStep | undefined = undefined; void _valuestreamstep;
    const _valuestreamwait: ValueStreamWait | undefined = undefined; void _valuestreamwait;
    const _valuestreamprops: ValueStreamProps | undefined = undefined; void _valuestreamprops;
    expect(true).toBe(true);
  });
});
