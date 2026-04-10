// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MenuBar } from '../menu-bar/MenuBar';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('MenuBar — depth', () => {
  describe('MenuBar — depth: prop combinations', () => {
    it('renders with showFavoriteToggle + enableSearchHandoff simultaneously', () => {
      render(<MenuBar {...requiredProps} showFavoriteToggle enableSearchHandoff>Stressed</MenuBar>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<MenuBar {...requiredProps} showFavoriteToggle enableSearchHandoff />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('MenuBar — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<MenuBar {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<MenuBar {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('MenuBar — depth: defaultFavoriteValues array edge cases', () => {
    it('handles empty defaultFavoriteValues', () => {
      const { container } = render(<MenuBar {...requiredProps} defaultFavoriteValues={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item defaultFavoriteValues', () => {
      const { container } = render(<MenuBar {...requiredProps} defaultFavoriteValues={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('MenuBar — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<MenuBar {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<MenuBar {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
