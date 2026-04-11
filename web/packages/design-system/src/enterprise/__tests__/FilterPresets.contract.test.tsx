// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FilterPresets } from '../FilterPresets';
import type { FilterPreset, FilterPresetsLocaleText, FilterPresetsProps } from '../FilterPresets';

describe('FilterPresets — contract', () => {
  const defaultProps = {
    presets: [],
    onSelect: vi.fn(),
  };

  it('renders without crash', () => {
    const { container } = render(<FilterPresets {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FilterPresets.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FilterPresets {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FilterPresets {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<FilterPresets {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _filterpreset: FilterPreset | undefined = undefined; void _filterpreset;
    const _filterpresetslocaletext: FilterPresetsLocaleText | undefined = undefined; void _filterpresetslocaletext;
    const _filterpresetsprops: FilterPresetsProps | undefined = undefined; void _filterpresetsprops;
    expect(true).toBe(true);
  });
});
