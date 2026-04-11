// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Descriptions } from '../descriptions/Descriptions';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('Descriptions — depth', () => {
  describe('Descriptions — depth: prop combinations', () => {
    it('renders with bordered', () => {
      const { container } = render(<Descriptions {...requiredProps} bordered />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Descriptions — depth: columns variants', () => {
    it.each(['1', '2', '3'] as const)('columns=%s renders without crash', (val) => {
      const { container } = render(<Descriptions {...requiredProps} columns={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Descriptions — depth: density variants', () => {
    it.each(['comfortable', 'compact'] as const)('density=%s renders without crash', (val) => {
      const { container } = render(<Descriptions {...requiredProps} density={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Descriptions — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Descriptions {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Descriptions {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
