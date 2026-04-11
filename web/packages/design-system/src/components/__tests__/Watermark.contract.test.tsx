// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Watermark } from '../watermark/Watermark';
import type { WatermarkProps, WatermarkRef, WatermarkElement, WatermarkCSSProperties } from '../watermark/Watermark';

describe('Watermark — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Watermark  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Watermark.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Watermark  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Watermark  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<Watermark  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _watermarkprops: WatermarkProps | undefined = undefined; void _watermarkprops;
    const _watermarkref: WatermarkRef | undefined = undefined; void _watermarkref;
    const _watermarkelement: WatermarkElement | undefined = undefined; void _watermarkelement;
    const _watermarkcssproperties: WatermarkCSSProperties | undefined = undefined; void _watermarkcssproperties;
    expect(true).toBe(true);
  });
});
