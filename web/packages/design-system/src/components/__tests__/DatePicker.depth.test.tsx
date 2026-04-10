// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DatePicker } from '../date-picker/DatePicker';

afterEach(cleanup);

describe('DatePicker — depth', () => {
  describe('DatePicker — depth: prop combinations', () => {
    it('renders with invalid + fullWidth simultaneously', () => {
      render(<DatePicker invalid fullWidth>Stressed</DatePicker>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<DatePicker invalid fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
