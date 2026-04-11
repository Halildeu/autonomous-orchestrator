// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { RecommendationCard } from '../recommendation-card/RecommendationCard';
import type { RecommendationCardTone, RecommendationCardProps } from '../recommendation-card/RecommendationCard';

describe('RecommendationCard — contract', () => {
  const defaultProps = {
    title: 'content',
    summary: 'content',
  };

  it('renders without crash', () => {
    const { container } = render(<RecommendationCard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(RecommendationCard.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<RecommendationCard {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<RecommendationCard {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 15 optional)', () => {
    // All 15 optional props omitted — should not crash
    const { container } = render(<RecommendationCard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _recommendationcardtone: RecommendationCardTone | undefined = undefined; void _recommendationcardtone;
    const _recommendationcardprops: RecommendationCardProps | undefined = undefined; void _recommendationcardprops;
    expect(true).toBe(true);
  });
});
