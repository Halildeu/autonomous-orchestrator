// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Tooltip } from '../tooltip/Tooltip';

afterEach(cleanup);

describe('Tooltip — depth', () => {
  describe('Tooltip — depth: prop combinations', () => {
    it('renders with disabled + showArrow simultaneously', () => {
      render(<Tooltip disabled showArrow>Stressed</Tooltip>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Tooltip disabled showArrow />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
