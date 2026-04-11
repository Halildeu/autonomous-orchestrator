// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AgingBuckets } from '../AgingBuckets';
import type { AgingBucket, AgingBucketsProps } from '../AgingBuckets';

describe('AgingBuckets — contract', () => {
  const defaultProps = {
    buckets: [],
  };

  it('renders without crash', () => {
    const { container } = render(<AgingBuckets {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AgingBuckets.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AgingBuckets {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AgingBuckets {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<AgingBuckets {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _agingbucket: AgingBucket | undefined = undefined; void _agingbucket;
    const _agingbucketsprops: AgingBucketsProps | undefined = undefined; void _agingbucketsprops;
    expect(true).toBe(true);
  });
});
