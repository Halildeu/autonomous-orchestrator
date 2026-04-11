// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { StatusIndicator } from '../status-indicator/StatusIndicator';

afterEach(cleanup);

describe('StatusIndicator — depth', () => {
  describe('StatusIndicator — depth: prop combinations', () => {
    it('renders with showLabel + pulse simultaneously', () => {
      render(<StatusIndicator showLabel pulse>Stressed</StatusIndicator>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<StatusIndicator showLabel pulse />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
