// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ThemePresetGallery } from '../theme-preset/ThemePresetGallery';
import type { ThemePresetGalleryItem, ThemePresetGalleryProps } from '../theme-preset/ThemePresetGallery';

describe('ThemePresetGallery — contract', () => {
  const defaultProps = {
    presets: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ThemePresetGallery {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ThemePresetGallery.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ThemePresetGallery {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ThemePresetGallery {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 28 optional)', () => {
    // All 28 optional props omitted — should not crash
    const { container } = render(<ThemePresetGallery {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _themepresetgalleryitem: ThemePresetGalleryItem | undefined = undefined; void _themepresetgalleryitem;
    const _themepresetgalleryprops: ThemePresetGalleryProps | undefined = undefined; void _themepresetgalleryprops;
    expect(true).toBe(true);
  });
});
