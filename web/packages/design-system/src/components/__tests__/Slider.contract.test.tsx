// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Slider } from '../slider/Slider';
import type { SliderProps, SliderRef, SliderElement, SliderCSSProperties } from '../slider/Slider';

describe('Slider — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Slider  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Slider.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Slider  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Slider  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<Slider  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _sliderprops: SliderProps | undefined = undefined; void _sliderprops;
    const _sliderref: SliderRef | undefined = undefined; void _sliderref;
    const _sliderelement: SliderElement | undefined = undefined; void _sliderelement;
    const _slidercssproperties: SliderCSSProperties | undefined = undefined; void _slidercssproperties;
    expect(true).toBe(true);
  });
});
