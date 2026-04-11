// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TourCoachmarks } from '../tour-coachmarks/TourCoachmarks';
import type { TourCoachmarkStep, TourCoachmarksProps } from '../tour-coachmarks/TourCoachmarks';

describe('TourCoachmarks — contract', () => {
  const defaultProps = {
    steps: [],
  };

  it('renders without crash', () => {
    const { container } = render(<TourCoachmarks {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TourCoachmarks.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TourCoachmarks {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TourCoachmarks {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 19 optional)', () => {
    // All 19 optional props omitted — should not crash
    const { container } = render(<TourCoachmarks {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _tourcoachmarkstep: TourCoachmarkStep | undefined = undefined; void _tourcoachmarkstep;
    const _tourcoachmarksprops: TourCoachmarksProps | undefined = undefined; void _tourcoachmarksprops;
    expect(true).toBe(true);
  });
});
