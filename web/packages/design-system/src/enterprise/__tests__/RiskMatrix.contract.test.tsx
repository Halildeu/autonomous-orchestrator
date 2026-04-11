// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { RiskMatrix } from '../RiskMatrix';
import type { RiskItem, RiskMatrixSize, RiskMatrixProps } from '../RiskMatrix';

describe('RiskMatrix — contract', () => {
  const defaultProps = {
    risks: [],
  };

  it('renders without crash', () => {
    const { container } = render(<RiskMatrix {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(RiskMatrix.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<RiskMatrix {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<RiskMatrix {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<RiskMatrix {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _riskitem: RiskItem | undefined = undefined; void _riskitem;
    const _riskmatrixsize: RiskMatrixSize | undefined = undefined; void _riskmatrixsize;
    const _riskmatrixprops: RiskMatrixProps | undefined = undefined; void _riskmatrixprops;
    expect(true).toBe(true);
  });
});
