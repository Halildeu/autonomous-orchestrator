// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { MetricComparisonCard } from '../MetricComparisonCard';
import type { MetricFormat, MetricSize, MetricComparisonCardProps } from '../MetricComparisonCard';

describe('MetricComparisonCard — contract', () => {
  const defaultProps = {
    title: 'test',
    currentValue: 42,
    previousValue: 42,
  };

  it('renders without crash', () => {
    const { container } = render(<MetricComparisonCard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(MetricComparisonCard.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<MetricComparisonCard {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<MetricComparisonCard {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _metricformat: MetricFormat | undefined = undefined; void _metricformat;
    const _metricsize: MetricSize | undefined = undefined; void _metricsize;
    const _metriccomparisoncardprops: MetricComparisonCardProps | undefined = undefined; void _metriccomparisoncardprops;
    expect(true).toBe(true);
  });
});
