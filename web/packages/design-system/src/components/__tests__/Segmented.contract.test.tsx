// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Segmented } from '../segmented/Segmented';
import type { SegmentedItem, SegmentedClasses, SegmentedProps, SegmentedPreset } from '../segmented/Segmented';

describe('Segmented — contract', () => {
  const defaultProps = {
    items: [],
    value: undefined as any,
    event: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<Segmented {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Segmented.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Segmented {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Segmented {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (3 required, 16 optional)', () => {
    // All 16 optional props omitted — should not crash
    const { container } = render(<Segmented {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _segmenteditem: SegmentedItem | undefined = undefined; void _segmenteditem;
    const _segmentedclasses: SegmentedClasses | undefined = undefined; void _segmentedclasses;
    const _segmentedprops: SegmentedProps | undefined = undefined; void _segmentedprops;
    const _segmentedpreset: SegmentedPreset | undefined = undefined; void _segmentedpreset;
    expect(true).toBe(true);
  });
});
