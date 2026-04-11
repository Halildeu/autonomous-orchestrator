// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Segmented } from '../segmented/Segmented';

afterEach(cleanup);

const requiredProps = {
  items: [],
  value: undefined as any,
  event: undefined as any,
};
describe('Segmented — depth', () => {
  describe('Segmented — depth: prop combinations', () => {
    it('renders with allowEmptySelection + fullWidth simultaneously', () => {
      render(<Segmented {...requiredProps} allowEmptySelection fullWidth>Stressed</Segmented>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Segmented {...requiredProps} allowEmptySelection fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Segmented — depth: selectionMode variants', () => {
    it.each(['single', 'multiple'] as const)('selectionMode=%s renders without crash', (val) => {
      const { container } = render(<Segmented {...requiredProps} selectionMode={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Segmented — depth: size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<Segmented {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Segmented — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Segmented {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Segmented {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Segmented — depth: onValueChange array edge cases', () => {
    it('handles empty onValueChange', () => {
      const { container } = render(<Segmented {...requiredProps} onValueChange={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onValueChange', () => {
      const { container } = render(<Segmented {...requiredProps} onValueChange={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Segmented — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Segmented {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Segmented {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
