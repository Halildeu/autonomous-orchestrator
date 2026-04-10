// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { NavigationRail } from '../navigation-rail/NavigationRail';

afterEach(cleanup);

const requiredProps = {
  items: [],
  value: undefined as any,
  event: undefined as any,
};
describe('NavigationRail — depth', () => {
  describe('NavigationRail — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<NavigationRail {...requiredProps} compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('NavigationRail — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<NavigationRail {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<NavigationRail {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('NavigationRail — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<NavigationRail {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<NavigationRail {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
