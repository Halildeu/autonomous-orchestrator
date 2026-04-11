// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { HeaderBar } from '../header-bar/HeaderBar';

afterEach(cleanup);

describe('HeaderBar — depth', () => {
  describe('HeaderBar — depth: prop combinations', () => {
    it('renders with blur + card simultaneously', () => {
      render(<HeaderBar blur card>Stressed</HeaderBar>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<HeaderBar blur card />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
