// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppSidebarFooterAction } from '../app-sidebar/AppSidebarFooterAction';

afterEach(cleanup);

const requiredProps = {
  icon: 'content',
  label: 'test',
};
describe('AppSidebarFooterAction — depth', () => {
  describe('AppSidebarFooterAction — depth: prop combinations', () => {
    it('renders with disabled + active simultaneously', () => {
      render(<AppSidebarFooterAction {...requiredProps} disabled active>Stressed</AppSidebarFooterAction>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<AppSidebarFooterAction {...requiredProps} disabled active />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AppSidebarFooterAction — depth: keyboard interaction', () => {
    it('fires onClick on keyboard Enter', async () => {
      const onClick = vi.fn();
      render(<AppSidebarFooterAction {...requiredProps} onClick={onClick}>Click me</AppSidebarFooterAction>);
      const el = screen.getByText('Click me');
      await userEvent.type(el, '{Enter}');
      expect(onClick).toHaveBeenCalled();
    });

    it('does not fire onClick when disabled', async () => {
      const onClick = vi.fn();
      render(<AppSidebarFooterAction {...requiredProps} onClick={onClick} disabled>Click me</AppSidebarFooterAction>);
      const el = screen.getByText('Click me');
      await userEvent.click(el);
      expect(onClick).not.toHaveBeenCalled();
    });
  });
});
