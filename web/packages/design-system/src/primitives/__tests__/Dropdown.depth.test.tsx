// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Dropdown } from '../dropdown/Dropdown';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('Dropdown — depth', () => {
  describe('Dropdown — depth: prop combinations', () => {
    it('renders with disabled', () => {
      const { container } = render(<Dropdown {...requiredProps} disabled />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Dropdown — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Dropdown {...requiredProps}>{null}</Dropdown>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Dropdown {...requiredProps}>{0}</Dropdown>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Dropdown {...requiredProps}>{''}</Dropdown>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Dropdown — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Dropdown {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Dropdown {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
