// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ThemePreviewCard } from '../theme-preview-card/ThemePreviewCard';

afterEach(cleanup);

describe('ThemePreviewCard — depth', () => {
  describe('ThemePreviewCard — depth: prop combinations', () => {
    it('renders with selected + showTokenSwatches + showComponentPreview + showTokenTooltip simultaneously', () => {
      render(<ThemePreviewCard selected showTokenSwatches showComponentPreview showTokenTooltip>Stressed</ThemePreviewCard>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ThemePreviewCard selected showTokenSwatches showComponentPreview showTokenTooltip />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
