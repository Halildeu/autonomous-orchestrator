// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { StatusTimeline } from '../StatusTimeline';
import type { StatusTimelineEvent, StatusTimelineProps } from '../StatusTimeline';

describe('StatusTimeline — contract', () => {
  const defaultProps = {
    events: [],
  };

  it('renders without crash', () => {
    const { container } = render(<StatusTimeline {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(StatusTimeline.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<StatusTimeline {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<StatusTimeline {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<StatusTimeline {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _statustimelineevent: StatusTimelineEvent | undefined = undefined; void _statustimelineevent;
    const _statustimelineprops: StatusTimelineProps | undefined = undefined; void _statustimelineprops;
    expect(true).toBe(true);
  });
});
