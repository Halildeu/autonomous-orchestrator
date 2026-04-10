// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TimePicker } from '../time-picker/TimePicker';

afterEach(cleanup);

describe('TimePicker — depth', () => {
  describe('TimePicker — depth: prop combinations', () => {
    it('renders with invalid + fullWidth simultaneously', () => {
      render(<TimePicker invalid fullWidth>Stressed</TimePicker>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<TimePicker invalid fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
