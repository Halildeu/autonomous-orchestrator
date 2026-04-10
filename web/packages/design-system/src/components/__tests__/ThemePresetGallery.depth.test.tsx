// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ThemePresetGallery } from '../theme-preset/ThemePresetGallery';

afterEach(cleanup);

const requiredProps = {
  presets: [],
};
describe('ThemePresetGallery — depth', () => {
  describe('ThemePresetGallery — depth: prop combinations', () => {
    it('renders with enableKeyboardNav + showFilters + showSearch + enableCompare simultaneously', () => {
      render(<ThemePresetGallery {...requiredProps} enableKeyboardNav showFilters showSearch enableCompare>Stressed</ThemePresetGallery>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ThemePresetGallery {...requiredProps} enableKeyboardNav showFilters showSearch enableCompare />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ThemePresetGallery — depth: previewSize variants', () => {
    it.each(['sm', 'md'] as const)('previewSize=%s renders without crash', (val) => {
      const { container } = render(<ThemePresetGallery {...requiredProps} previewSize={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ThemePresetGallery — depth: presets array edge cases', () => {
    it('handles empty presets', () => {
      const { container } = render(<ThemePresetGallery {...requiredProps} presets={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item presets', () => {
      const { container } = render(<ThemePresetGallery {...requiredProps} presets={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ThemePresetGallery — depth: compareAxes array edge cases', () => {
    it('handles empty compareAxes', () => {
      const { container } = render(<ThemePresetGallery {...requiredProps} compareAxes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item compareAxes', () => {
      const { container } = render(<ThemePresetGallery {...requiredProps} compareAxes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
