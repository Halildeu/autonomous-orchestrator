// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SummaryStrip } from '../summary-strip/SummaryStrip';
import type { SummaryStripItem, SummaryStripProps } from '../summary-strip/SummaryStrip';

describe('SummaryStrip — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<SummaryStrip {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SummaryStrip.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<SummaryStrip {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<SummaryStrip {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<SummaryStrip {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _summarystripitem: SummaryStripItem | undefined = undefined; void _summarystripitem;
    const _summarystripprops: SummaryStripProps | undefined = undefined; void _summarystripprops;
    expect(true).toBe(true);
  });
});
