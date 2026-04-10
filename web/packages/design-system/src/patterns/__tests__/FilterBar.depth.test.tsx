// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FilterBar } from '../filter-bar/FilterBar';

afterEach(cleanup);

describe('FilterBar — depth', () => {
  describe('FilterBar — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<FilterBar compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FilterBar — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<FilterBar>{null}</FilterBar>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<FilterBar>{0}</FilterBar>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<FilterBar>{''}</FilterBar>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
