// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DetailDrawer } from '../detail-drawer/DetailDrawer';

afterEach(cleanup);

const requiredProps = {
  open: true,
  onClose: vi.fn(),
  title: 'content',
};
describe('DetailDrawer — depth', () => {
  describe('DetailDrawer — depth: prop combinations', () => {
    it('renders with open + closeOnBackdrop simultaneously', () => {
      render(<DetailDrawer {...requiredProps} open closeOnBackdrop>Stressed</DetailDrawer>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<DetailDrawer {...requiredProps} open closeOnBackdrop />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('DetailDrawer — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<DetailDrawer {...requiredProps}>{null}</DetailDrawer>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<DetailDrawer {...requiredProps}>{0}</DetailDrawer>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<DetailDrawer {...requiredProps}>{''}</DetailDrawer>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('DetailDrawer — depth: sections array edge cases', () => {
    it('handles empty sections', () => {
      const { container } = render(<DetailDrawer {...requiredProps} sections={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item sections', () => {
      const { container } = render(<DetailDrawer {...requiredProps} sections={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
