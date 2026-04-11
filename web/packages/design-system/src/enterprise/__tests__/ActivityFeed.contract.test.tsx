// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ActivityFeed } from '../ActivityFeed';
import type { ActivityItem, ActivityFeedProps } from '../ActivityFeed';

describe('ActivityFeed — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ActivityFeed {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ActivityFeed.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ActivityFeed {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ActivityFeed {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<ActivityFeed {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _activityitem: ActivityItem | undefined = undefined; void _activityitem;
    const _activityfeedprops: ActivityFeedProps | undefined = undefined; void _activityfeedprops;
    expect(true).toBe(true);
  });
});
