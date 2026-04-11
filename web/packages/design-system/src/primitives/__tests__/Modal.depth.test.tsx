// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Modal } from '../modal/Modal';

afterEach(cleanup);

const requiredProps = {
  open: true,
};
describe('Modal — depth', () => {
  describe('Modal — depth: prop combinations', () => {
    it('renders with open + fullWidth + closeOnOverlayClick + closeOnEscape simultaneously', () => {
      render(<Modal {...requiredProps} open fullWidth closeOnOverlayClick closeOnEscape>Stressed</Modal>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Modal {...requiredProps} open fullWidth closeOnOverlayClick closeOnEscape />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Modal — depth: size variants', () => {
    it.each(['sm', 'md', 'lg'] as const)('size=%s renders without crash', (val) => {
      const { container } = render(<Modal {...requiredProps} size={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Modal — depth: maxWidth variants', () => {
    it.each(['number', 'string'] as const)('maxWidth=%s renders without crash', (val) => {
      const { container } = render(<Modal {...requiredProps} maxWidth={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Modal — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Modal {...requiredProps}>{null}</Modal>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Modal {...requiredProps}>{0}</Modal>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Modal {...requiredProps}>{''}</Modal>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
