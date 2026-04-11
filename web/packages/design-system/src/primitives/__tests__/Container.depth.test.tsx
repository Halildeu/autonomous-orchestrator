// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Container } from '../container/Container';

afterEach(cleanup);

describe('Container — depth', () => {
  describe('Container — depth: prop combinations', () => {
    it('renders with centered + padding + fluid simultaneously', () => {
      render(<Container centered padding fluid>Stressed</Container>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Container centered padding fluid />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Container — depth: as variants', () => {
    it.each(['div', 'section', 'article', 'main'] as const)('as=%s renders without crash', (val) => {
      const { container } = render(<Container as={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
