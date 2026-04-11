// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { MasterDetail } from '../master-detail/MasterDetail';
import type { MasterDetailRatio, MasterDetailProps } from '../master-detail/MasterDetail';

describe('MasterDetail — contract', () => {
  const defaultProps = {
    master: 'content',
    detail: 'content',
  };

  it('renders without crash', () => {
    const { container } = render(<MasterDetail {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(MasterDetail.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<MasterDetail {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<MasterDetail {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<MasterDetail {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _masterdetailratio: MasterDetailRatio | undefined = undefined; void _masterdetailratio;
    const _masterdetailprops: MasterDetailProps | undefined = undefined; void _masterdetailprops;
    expect(true).toBe(true);
  });
});
