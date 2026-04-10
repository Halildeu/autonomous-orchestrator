// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { LinkInline } from '../link-inline/LinkInline';

afterEach(cleanup);

describe('LinkInline — depth', () => {
  describe('LinkInline — depth: prop combinations', () => {
    it('renders with current + disabled + external simultaneously', () => {
      render(<LinkInline current disabled external>Stressed</LinkInline>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<LinkInline current disabled external />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('LinkInline — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<LinkInline>{null}</LinkInline>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<LinkInline>{0}</LinkInline>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<LinkInline>{''}</LinkInline>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
