// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Rating } from '../rating/Rating';
import type { RatingSize, RatingProps } from '../rating/Rating';

describe('Rating — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Rating  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Rating.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Rating  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Rating  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 12 optional)', () => {
    // All 12 optional props omitted — should not crash
    const { container } = render(<Rating  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _ratingsize: RatingSize | undefined = undefined; void _ratingsize;
    const _ratingprops: RatingProps | undefined = undefined; void _ratingprops;
    expect(true).toBe(true);
  });
});
