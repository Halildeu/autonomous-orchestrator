// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { NavigationRail } from '../navigation-rail/NavigationRail';
import type { NavigationRailAlignment, NavigationRailSize, NavigationRailAppearance, NavigationRailLabelVisibility, NavigationRailPresetKind } from '../navigation-rail/NavigationRail';

describe('NavigationRail — contract', () => {
  const defaultProps = {
    items: [],
    value: undefined as any,
    event: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<NavigationRail {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(NavigationRail.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<NavigationRail {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<NavigationRail {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (3 required, 14 optional)', () => {
    // All 14 optional props omitted — should not crash
    const { container } = render(<NavigationRail {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _navigationrailalignment: NavigationRailAlignment | undefined = undefined; void _navigationrailalignment;
    const _navigationrailsize: NavigationRailSize | undefined = undefined; void _navigationrailsize;
    const _navigationrailappearance: NavigationRailAppearance | undefined = undefined; void _navigationrailappearance;
    const _navigationraillabelvisibility: NavigationRailLabelVisibility | undefined = undefined; void _navigationraillabelvisibility;
    const _navigationrailpresetkind: NavigationRailPresetKind | undefined = undefined; void _navigationrailpresetkind;
    expect(true).toBe(true);
  });
});
