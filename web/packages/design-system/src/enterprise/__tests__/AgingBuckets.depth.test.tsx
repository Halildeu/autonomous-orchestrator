// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AgingBuckets } from '../AgingBuckets';

afterEach(cleanup);

const requiredProps = {
  buckets: [],
};
describe('AgingBuckets — depth', () => {
  describe('AgingBuckets — depth: prop combinations', () => {
    it('renders with showStackedBar', () => {
      const { container } = render(<AgingBuckets {...requiredProps} showStackedBar />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AgingBuckets — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<AgingBuckets {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AgingBuckets — depth: buckets array edge cases', () => {
    it('handles empty buckets', () => {
      const { container } = render(<AgingBuckets {...requiredProps} buckets={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item buckets', () => {
      const { container } = render(<AgingBuckets {...requiredProps} buckets={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
