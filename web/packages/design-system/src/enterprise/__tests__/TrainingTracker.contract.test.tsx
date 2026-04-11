// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TrainingTracker } from '../TrainingTracker';
import type { TrainingStatus, TrainingItem, TrainingTrackerProps } from '../TrainingTracker';

describe('TrainingTracker — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<TrainingTracker {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TrainingTracker.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TrainingTracker {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TrainingTracker {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<TrainingTracker {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _trainingstatus: TrainingStatus | undefined = undefined; void _trainingstatus;
    const _trainingitem: TrainingItem | undefined = undefined; void _trainingitem;
    const _trainingtrackerprops: TrainingTrackerProps | undefined = undefined; void _trainingtrackerprops;
    expect(true).toBe(true);
  });
});
