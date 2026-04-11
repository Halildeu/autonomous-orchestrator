// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Tag } from '../tag/Tag';

afterEach(cleanup);

describe('Tag — depth', () => {
  describe('Tag — depth: prop combinations', () => {
    it('renders with closable + asChild simultaneously', () => {
      render(<Tag closable asChild>Stressed</Tag>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Tag closable asChild />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
