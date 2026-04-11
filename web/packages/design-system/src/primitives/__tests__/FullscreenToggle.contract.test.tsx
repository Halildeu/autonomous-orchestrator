// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FullscreenToggle } from '../fullscreen-toggle/FullscreenToggle';
import type { FullscreenToggleSize, FullscreenToggleVariant, FullscreenToggleProps } from '../fullscreen-toggle/FullscreenToggle';

describe('FullscreenToggle — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<FullscreenToggle  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<FullscreenToggle  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _fullscreentogglesize: FullscreenToggleSize | undefined = undefined; void _fullscreentogglesize;
    const _fullscreentogglevariant: FullscreenToggleVariant | undefined = undefined; void _fullscreentogglevariant;
    const _fullscreentoggleprops: FullscreenToggleProps | undefined = undefined; void _fullscreentoggleprops;
    expect(true).toBe(true);
  });
});
