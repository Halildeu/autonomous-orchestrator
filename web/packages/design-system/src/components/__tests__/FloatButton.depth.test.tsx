// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FloatButton } from '../float-button/FloatButton';

afterEach(cleanup);

describe('FloatButton — depth', () => {
  describe('FloatButton — depth: prop combinations', () => {
    it('renders with open', () => {
      const { container } = render(<FloatButton open />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FloatButton — depth: badge variants', () => {
    it.each(['number', 'boolean'] as const)('badge=%s renders without crash', (val) => {
      const { container } = render(<FloatButton badge={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FloatButton — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<FloatButton items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<FloatButton items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FloatButton — depth: keyboard interaction', () => {
    it('fires onClick on keyboard Enter', async () => {
      const onClick = vi.fn();
      render(<FloatButton onClick={onClick}>Click me</FloatButton>);
      const el = screen.getByText('Click me');
      await userEvent.type(el, '{Enter}');
      expect(onClick).toHaveBeenCalled();
    });

    it('does not fire onClick when disabled', async () => {
      const onClick = vi.fn();
      render(<FloatButton onClick={onClick} disabled>Click me</FloatButton>);
      const el = screen.getByText('Click me');
      await userEvent.click(el);
      expect(onClick).not.toHaveBeenCalled();
    });
  });
});
