// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Timeline } from '../timeline/Timeline';
import type { TimelineColor, TimelineMode, TimelineSize, TimelineItemProps, TimelineProps } from '../timeline/Timeline';

describe('Timeline — contract', () => {
  const defaultProps = {
    key: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<Timeline {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Timeline.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Timeline {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Timeline {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<Timeline {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _timelinecolor: TimelineColor | undefined = undefined; void _timelinecolor;
    const _timelinemode: TimelineMode | undefined = undefined; void _timelinemode;
    const _timelinesize: TimelineSize | undefined = undefined; void _timelinesize;
    const _timelineitemprops: TimelineItemProps | undefined = undefined; void _timelineitemprops;
    const _timelineprops: TimelineProps | undefined = undefined; void _timelineprops;
    expect(true).toBe(true);
  });
});
