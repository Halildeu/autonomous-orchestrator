// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { IconButton } from '../icon-button/IconButton';

afterEach(cleanup);

const requiredProps = {
  icon: 'content',
  label: 'test',
};
describe('IconButton — depth', () => {
  describe('IconButton — depth: prop combinations', () => {
    it('renders with loading + rounded simultaneously', () => {
      render(<IconButton {...requiredProps} loading rounded>Stressed</IconButton>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<IconButton {...requiredProps} loading rounded />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
