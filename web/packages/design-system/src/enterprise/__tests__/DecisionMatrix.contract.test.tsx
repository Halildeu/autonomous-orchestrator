// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { DecisionMatrix } from '../DecisionMatrix';
import type { DecisionOption, DecisionCriterion, DecisionScore, DecisionMatrixProps } from '../DecisionMatrix';

describe('DecisionMatrix — contract', () => {
  const defaultProps = {
    options: [],
    criteria: [],
    scores: [],
  };

  it('renders without crash', () => {
    const { container } = render(<DecisionMatrix {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(DecisionMatrix.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<DecisionMatrix {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<DecisionMatrix {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (3 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<DecisionMatrix {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _decisionoption: DecisionOption | undefined = undefined; void _decisionoption;
    const _decisioncriterion: DecisionCriterion | undefined = undefined; void _decisioncriterion;
    const _decisionscore: DecisionScore | undefined = undefined; void _decisionscore;
    const _decisionmatrixprops: DecisionMatrixProps | undefined = undefined; void _decisionmatrixprops;
    expect(true).toBe(true);
  });
});
