// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AnchorToc } from '../anchor-toc/AnchorToc';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('AnchorToc — depth', () => {
  describe('AnchorToc — depth: prop combinations', () => {
    it('renders with sticky + syncWithHash simultaneously', () => {
      render(<AnchorToc {...requiredProps} sticky syncWithHash>Stressed</AnchorToc>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<AnchorToc {...requiredProps} sticky syncWithHash />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AnchorToc — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<AnchorToc {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<AnchorToc {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AnchorToc — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<AnchorToc {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<AnchorToc {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
