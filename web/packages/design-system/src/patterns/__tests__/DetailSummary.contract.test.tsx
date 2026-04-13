// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { DetailSummary } from '../detail-summary/DetailSummary';
import type { DetailSummaryProps, DetailSummaryRef, DetailSummaryElement, DetailSummaryCSSProperties } from '../detail-summary/DetailSummary';

describe('DetailSummary — contract', () => {
  const defaultProps = {
    title: 'content',
    entity: { title: 'Entity', items: [{ label: 'Status', value: 'Active' }] },
  };

  it('renders without crash', () => {
    const { container } = render(<DetailSummary {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(DetailSummary.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<DetailSummary {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<DetailSummary {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 14 optional)', () => {
    // All 14 optional props omitted — should not crash
    const { container } = render(<DetailSummary {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _detailsummaryprops: DetailSummaryProps | undefined = undefined; void _detailsummaryprops;
    const _detailsummaryref: DetailSummaryRef | undefined = undefined; void _detailsummaryref;
    const _detailsummaryelement: DetailSummaryElement | undefined = undefined; void _detailsummaryelement;
    const _detailsummarycssproperties: DetailSummaryCSSProperties | undefined = undefined; void _detailsummarycssproperties;
    expect(true).toBe(true);
  });
});
