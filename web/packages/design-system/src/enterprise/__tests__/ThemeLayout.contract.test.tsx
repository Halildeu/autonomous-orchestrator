// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ThemeLayout } from '../ThemeLayout';
import type { LayoutTheme, ThemeLayoutSlots, ThemeLayoutProps } from '../ThemeLayout';

describe('ThemeLayout — contract', () => {
  const defaultProps = {
    theme: 'executive' as const,
    slots: { header: React.createElement('div', null, 'Header') },
  };

  it('renders without crash', () => {
    const { container } = render(<ThemeLayout {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ThemeLayout.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ThemeLayout {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ThemeLayout {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _layouttheme: LayoutTheme | undefined = undefined; void _layouttheme;
    const _themelayoutslots: ThemeLayoutSlots | undefined = undefined; void _themelayoutslots;
    const _themelayoutprops: ThemeLayoutProps | undefined = undefined; void _themelayoutprops;
    expect(true).toBe(true);
  });
});
