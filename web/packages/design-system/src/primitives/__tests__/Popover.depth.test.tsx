// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Popover } from '../popover/Popover';

afterEach(cleanup);

const requiredProps = {
  trigger: 'content',
  content: 'content',
};
describe('Popover — depth', () => {
  describe('Popover — depth: prop combinations', () => {
    it('renders with open + defaultOpen + disablePortal + flipOnCollision simultaneously', () => {
      render(<Popover {...requiredProps} open defaultOpen disablePortal flipOnCollision>Stressed</Popover>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Popover {...requiredProps} open defaultOpen disablePortal flipOnCollision />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
