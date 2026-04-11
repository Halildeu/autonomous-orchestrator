// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ColorPicker } from '../color-picker/ColorPicker';
import type { ColorPickerFormat, ColorPickerSize, ColorPickerPreset, ColorPickerProps } from '../color-picker/ColorPicker';

describe('ColorPicker — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ColorPicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ColorPicker.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ColorPicker  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ColorPicker  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<ColorPicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _colorpickerformat: ColorPickerFormat | undefined = undefined; void _colorpickerformat;
    const _colorpickersize: ColorPickerSize | undefined = undefined; void _colorpickersize;
    const _colorpickerpreset: ColorPickerPreset | undefined = undefined; void _colorpickerpreset;
    const _colorpickerprops: ColorPickerProps | undefined = undefined; void _colorpickerprops;
    expect(true).toBe(true);
  });
});
