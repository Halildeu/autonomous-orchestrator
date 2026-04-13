// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Slot } from '../_shared/Slot';
import type { SlotProps, SlotRef, SlotElement, SlotCSSProperties } from '../_shared/Slot';

describe('Slot — contract', () => {

  it('renders without crash', () => {
    // Slot requires exactly one child element (React.Children.only)
    const { container } = render(<Slot><span>child</span></Slot>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Slot.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    const { container } = render(<Slot><span>child</span></Slot>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _slotprops: SlotProps | undefined = undefined; void _slotprops;
    const _slotref: SlotRef | undefined = undefined; void _slotref;
    const _slotelement: SlotElement | undefined = undefined; void _slotelement;
    const _slotcssproperties: SlotCSSProperties | undefined = undefined; void _slotcssproperties;
    expect(true).toBe(true);
  });
});
