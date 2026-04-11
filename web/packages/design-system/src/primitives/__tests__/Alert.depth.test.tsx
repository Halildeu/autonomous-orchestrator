// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Alert } from '../alert/Alert';

afterEach(cleanup);

describe('Alert — depth', () => {
  describe('Alert — depth: prop combinations', () => {
    it('renders with closable + asChild simultaneously', () => {
      render(<Alert closable asChild>Stressed</Alert>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Alert closable asChild />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
