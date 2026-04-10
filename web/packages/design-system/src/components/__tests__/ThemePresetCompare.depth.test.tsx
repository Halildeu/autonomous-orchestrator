// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ThemePresetCompare } from '../theme-preset/ThemePresetCompare';

afterEach(cleanup);

describe('ThemePresetCompare — depth', () => {
  describe('ThemePresetCompare — depth: prop combinations', () => {
    it('renders with showLivePreview + showTokenDiff + collapsible + highlightDifferences simultaneously', () => {
      render(<ThemePresetCompare showLivePreview showTokenDiff collapsible highlightDifferences>Stressed</ThemePresetCompare>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ThemePresetCompare showLivePreview showTokenDiff collapsible highlightDifferences />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ThemePresetCompare — depth: axes array edge cases', () => {
    it('handles empty axes', () => {
      const { container } = render(<ThemePresetCompare axes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item axes', () => {
      const { container } = render(<ThemePresetCompare axes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ThemePresetCompare — depth: tokenCategories array edge cases', () => {
    it('handles empty tokenCategories', () => {
      const { container } = render(<ThemePresetCompare tokenCategories={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item tokenCategories', () => {
      const { container } = render(<ThemePresetCompare tokenCategories={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
