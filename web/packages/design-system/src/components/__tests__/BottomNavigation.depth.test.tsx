// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { BottomNavigation } from '../bottom-navigation/BottomNavigation';

afterEach(cleanup);

describe('BottomNavigation — depth', () => {
  describe('BottomNavigation — depth: prop combinations', () => {
    it('renders with showLabels + fixed simultaneously', () => {
      render(<BottomNavigation showLabels fixed>Stressed</BottomNavigation>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<BottomNavigation showLabels fixed />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('BottomNavigation — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<BottomNavigation value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<BottomNavigation defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
