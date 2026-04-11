// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Mentions } from '../mentions/Mentions';

afterEach(cleanup);

const requiredProps = {
  options: [],
};
describe('Mentions — depth', () => {
  describe('Mentions — depth: prop combinations', () => {
    it('renders with error', () => {
      const { container } = render(<Mentions {...requiredProps} error />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Mentions — depth: size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<Mentions {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Mentions — depth: options array edge cases', () => {
    it('handles empty options', () => {
      const { container } = render(<Mentions {...requiredProps} options={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item options', () => {
      const { container } = render(<Mentions {...requiredProps} options={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Mentions — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Mentions {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Mentions {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
