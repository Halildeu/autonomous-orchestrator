// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Image } from '../image/Image';
import type { ImageRounded, ImageObjectFit, ImagePreviewConfig, ImageProps, ImageGroupProps } from '../image/Image';

describe('Image — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Image  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Image.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<Image  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _imagerounded: ImageRounded | undefined = undefined; void _imagerounded;
    const _imageobjectfit: ImageObjectFit | undefined = undefined; void _imageobjectfit;
    const _imagepreviewconfig: ImagePreviewConfig | undefined = undefined; void _imagepreviewconfig;
    const _imageprops: ImageProps | undefined = undefined; void _imageprops;
    const _imagegroupprops: ImageGroupProps | undefined = undefined; void _imagegroupprops;
    expect(true).toBe(true);
  });
});
