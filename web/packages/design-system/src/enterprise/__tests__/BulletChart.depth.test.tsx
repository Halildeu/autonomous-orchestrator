// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { BulletChart } from '../BulletChart';

afterEach(cleanup);

const requiredProps = {
  value: 42,
  target: 42,
};
describe('BulletChart — depth', () => {
  describe('BulletChart — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<BulletChart {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BulletChart — depth: size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<BulletChart {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BulletChart — depth: ranges array edge cases', () => {
    it('handles empty ranges', () => {
      const { container } = render(<BulletChart {...requiredProps} ranges={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item ranges', () => {
      const { container } = render(<BulletChart {...requiredProps} ranges={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
