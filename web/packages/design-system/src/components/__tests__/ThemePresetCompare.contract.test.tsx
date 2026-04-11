// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ThemePresetCompare } from '../theme-preset/ThemePresetCompare';
import type { ThemePresetCompareProps, ThemePresetCompareRef, ThemePresetCompareElement, ThemePresetCompareCSSProperties } from '../theme-preset/ThemePresetCompare';

describe('ThemePresetCompare — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ThemePresetCompare  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ThemePresetCompare.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ThemePresetCompare  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ThemePresetCompare  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 23 optional)', () => {
    // All 23 optional props omitted — should not crash
    const { container } = render(<ThemePresetCompare  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _themepresetcompareprops: ThemePresetCompareProps | undefined = undefined; void _themepresetcompareprops;
    const _themepresetcompareref: ThemePresetCompareRef | undefined = undefined; void _themepresetcompareref;
    const _themepresetcompareelement: ThemePresetCompareElement | undefined = undefined; void _themepresetcompareelement;
    const _themepresetcomparecssproperties: ThemePresetCompareCSSProperties | undefined = undefined; void _themepresetcomparecssproperties;
    expect(true).toBe(true);
  });
});
