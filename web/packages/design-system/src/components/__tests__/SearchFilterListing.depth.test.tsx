// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SearchFilterListing } from '../search-filter-listing/SearchFilterListing';

afterEach(cleanup);

const requiredProps = {
  title: 'content',
};
describe('SearchFilterListing — depth', () => {
  describe('SearchFilterListing — depth: prop combinations', () => {
    it('renders with selectable + loading simultaneously', () => {
      render(<SearchFilterListing {...requiredProps} selectable loading>Stressed</SearchFilterListing>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<SearchFilterListing {...requiredProps} selectable loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SearchFilterListing — depth: size variants', () => {
    it.each(['default', 'compact'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<SearchFilterListing {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SearchFilterListing — depth: activeFilters array edge cases', () => {
    it('handles empty activeFilters', () => {
      const { container } = render(<SearchFilterListing {...requiredProps} activeFilters={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item activeFilters', () => {
      const { container } = render(<SearchFilterListing {...requiredProps} activeFilters={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SearchFilterListing — depth: summaryItems array edge cases', () => {
    it('handles empty summaryItems', () => {
      const { container } = render(<SearchFilterListing {...requiredProps} summaryItems={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item summaryItems', () => {
      const { container } = render(<SearchFilterListing {...requiredProps} summaryItems={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
