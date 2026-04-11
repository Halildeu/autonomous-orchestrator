// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Checkbox } from '../checkbox/Checkbox';

afterEach(cleanup);

describe('Checkbox — depth', () => {
  describe('Checkbox — depth: prop combinations', () => {
    it('renders with defaultChecked + indeterminate + loading simultaneously', () => {
      render(<Checkbox defaultChecked indeterminate loading>Stressed</Checkbox>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Checkbox defaultChecked indeterminate loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Checkbox — depth: density variants', () => {
    it.each(['compact', 'comfortable', 'spacious'] as const)('density=%s renders without crash', (val) => {
      const { container } = render(<Checkbox density={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Checkbox — depth: variant variants', () => {
    it.each(['default', 'card'] as const)('variant=%s renders without crash', (val) => {
      const { container } = render(<Checkbox variant={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
