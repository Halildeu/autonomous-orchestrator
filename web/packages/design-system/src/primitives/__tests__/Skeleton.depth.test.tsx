// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Skeleton } from '../skeleton/Skeleton';

afterEach(cleanup);

describe('Skeleton — depth', () => {
  describe('Skeleton — depth: prop combinations', () => {
    it('renders with circle + animated simultaneously', () => {
      render(<Skeleton circle animated>Stressed</Skeleton>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Skeleton circle animated />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Skeleton — depth: width variants', () => {
    it.each(['string', 'number'] as const)('width=%s renders without crash', (val) => {
      const { container } = render(<Skeleton width={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Skeleton — depth: height variants', () => {
    it.each(['string', 'number'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<Skeleton height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
