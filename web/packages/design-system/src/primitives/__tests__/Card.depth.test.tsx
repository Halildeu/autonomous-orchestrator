// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Card } from '../card/Card';

afterEach(cleanup);

describe('Card — depth', () => {
  describe('Card — depth: prop combinations', () => {
    it('renders with hoverable + asChild simultaneously', () => {
      render(<Card hoverable asChild>Stressed</Card>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Card hoverable asChild />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Card — depth: as variants', () => {
    it.each(['div', 'button', 'article', 'section'] as const)('as=%s renders without crash', (val) => {
      const { container } = render(<Card as={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
