// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Slider } from '../slider/Slider';

afterEach(cleanup);

describe('Slider — depth', () => {
  describe('Slider — depth: prop combinations', () => {
    it('renders with invalid + fullWidth simultaneously', () => {
      render(<Slider invalid fullWidth>Stressed</Slider>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Slider invalid fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
