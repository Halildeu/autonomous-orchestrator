// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Divider } from '../divider/Divider';
import type { DividerProps, DividerRef, DividerElement, DividerCSSProperties } from '../divider/Divider';

describe('Divider — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Divider  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Divider.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<Divider  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _dividerprops: DividerProps | undefined = undefined; void _dividerprops;
    const _dividerref: DividerRef | undefined = undefined; void _dividerref;
    const _dividerelement: DividerElement | undefined = undefined; void _dividerelement;
    const _dividercssproperties: DividerCSSProperties | undefined = undefined; void _dividercssproperties;
    expect(true).toBe(true);
  });
});
