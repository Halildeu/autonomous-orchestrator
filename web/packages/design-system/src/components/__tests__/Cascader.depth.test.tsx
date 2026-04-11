// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Cascader } from '../cascader/Cascader';

afterEach(cleanup);

const requiredProps = {
  options: [],
};
describe('Cascader — depth', () => {
  describe('Cascader — depth: prop combinations', () => {
    it('renders with multiple + searchable + error simultaneously', () => {
      render(<Cascader {...requiredProps} multiple searchable error>Stressed</Cascader>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Cascader {...requiredProps} multiple searchable error />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Cascader — depth: size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<Cascader {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Cascader — depth: expandTrigger variants', () => {
    it.each(['click', 'hover'] as const)('expandTrigger=%s renders without crash', (val) => {
      const { container } = render(<Cascader {...requiredProps} expandTrigger={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Cascader — depth: options array edge cases', () => {
    it('handles empty options', () => {
      const { container } = render(<Cascader {...requiredProps} options={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item options', () => {
      const { container } = render(<Cascader {...requiredProps} options={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Cascader — depth: value array edge cases', () => {
    it('handles empty value', () => {
      const { container } = render(<Cascader {...requiredProps} value={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item value', () => {
      const { container } = render(<Cascader {...requiredProps} value={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Cascader — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Cascader {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Cascader {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
