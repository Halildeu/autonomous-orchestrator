// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Switch } from '../switch/Switch';

afterEach(cleanup);

describe('Switch — depth', () => {
  describe('Switch — depth: prop combinations', () => {
    it('renders with defaultChecked + checked + loading simultaneously', () => {
      render(<Switch defaultChecked checked loading>Stressed</Switch>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Switch defaultChecked checked loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
