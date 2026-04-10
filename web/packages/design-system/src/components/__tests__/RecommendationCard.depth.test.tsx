// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { RecommendationCard } from '../recommendation-card/RecommendationCard';

afterEach(cleanup);

const requiredProps = {
  title: 'content',
  summary: 'content',
};
describe('RecommendationCard — depth', () => {
  describe('RecommendationCard — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<RecommendationCard {...requiredProps} compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('RecommendationCard — depth: rationale array edge cases', () => {
    it('handles empty rationale', () => {
      const { container } = render(<RecommendationCard {...requiredProps} rationale={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item rationale', () => {
      const { container } = render(<RecommendationCard {...requiredProps} rationale={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('RecommendationCard — depth: citations array edge cases', () => {
    it('handles empty citations', () => {
      const { container } = render(<RecommendationCard {...requiredProps} citations={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item citations', () => {
      const { container } = render(<RecommendationCard {...requiredProps} citations={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
