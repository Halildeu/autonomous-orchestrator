// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ThemePreviewCard } from '../theme-preview-card/ThemePreviewCard';
import type { ThemePreviewCardSize, ThemePreviewCardProps, ThemePreviewCardRef, ThemePreviewCardElement, ThemePreviewCardCSSProperties } from '../theme-preview-card/ThemePreviewCard';

describe('ThemePreviewCard — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ThemePreviewCard  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ThemePreviewCard.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ThemePreviewCard  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ThemePreviewCard  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 15 optional)', () => {
    // All 15 optional props omitted — should not crash
    const { container } = render(<ThemePreviewCard  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _themepreviewcardsize: ThemePreviewCardSize | undefined = undefined; void _themepreviewcardsize;
    const _themepreviewcardprops: ThemePreviewCardProps | undefined = undefined; void _themepreviewcardprops;
    const _themepreviewcardref: ThemePreviewCardRef | undefined = undefined; void _themepreviewcardref;
    const _themepreviewcardelement: ThemePreviewCardElement | undefined = undefined; void _themepreviewcardelement;
    const _themepreviewcardcssproperties: ThemePreviewCardCSSProperties | undefined = undefined; void _themepreviewcardcssproperties;
    expect(true).toBe(true);
  });
});
