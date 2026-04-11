// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Select } from '../select/Select';

afterEach(cleanup);

const requiredProps = {
  options: [],
};
describe('Select — depth', () => {
  describe('Select — depth: prop combinations', () => {
    it('renders with fullWidth + loading simultaneously', () => {
      render(<Select {...requiredProps} fullWidth loading>Stressed</Select>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Select {...requiredProps} fullWidth loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Select — depth: options array edge cases', () => {
    it('handles empty options', () => {
      const { container } = render(<Select {...requiredProps} options={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item options', () => {
      const { container } = render(<Select {...requiredProps} options={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
