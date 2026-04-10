// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AvatarGroup } from '../avatar-group/AvatarGroup';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('AvatarGroup — depth', () => {
  describe('AvatarGroup — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<AvatarGroup {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<AvatarGroup {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AvatarGroup — depth: keyboard interaction', () => {
    it('fires onClick on keyboard Enter', async () => {
      const onClick = vi.fn();
      render(<AvatarGroup {...requiredProps} onClick={onClick}>Click me</AvatarGroup>);
      const el = screen.getByText('Click me');
      await userEvent.type(el, '{Enter}');
      expect(onClick).toHaveBeenCalled();
    });

    it('does not fire onClick when disabled', async () => {
      const onClick = vi.fn();
      render(<AvatarGroup {...requiredProps} onClick={onClick} disabled>Click me</AvatarGroup>);
      const el = screen.getByText('Click me');
      await userEvent.click(el);
      expect(onClick).not.toHaveBeenCalled();
    });
  });
});
