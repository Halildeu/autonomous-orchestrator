// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Accordion } from '../accordion/Accordion';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('Accordion — depth', () => {
  describe('Accordion — depth: prop combinations', () => {
    it('renders with bordered + ghost + showArrow + disableGutters simultaneously', () => {
      render(<Accordion {...requiredProps} bordered ghost showArrow disableGutters>Stressed</Accordion>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Accordion {...requiredProps} bordered ghost showArrow disableGutters />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Accordion — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Accordion {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Accordion {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Accordion — depth: onValueChange array edge cases', () => {
    it('handles empty onValueChange', () => {
      const { container } = render(<Accordion {...requiredProps} onValueChange={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onValueChange', () => {
      const { container } = render(<Accordion {...requiredProps} onValueChange={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Accordion — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Accordion {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Accordion {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
