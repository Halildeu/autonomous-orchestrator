// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FloatButton } from '../float-button/FloatButton';
import type { FloatButtonShape, FloatButtonSize, FloatButtonPosition, FloatButtonTrigger, FloatButtonGroupItem } from '../float-button/FloatButton';

describe('FloatButton — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<FloatButton  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FloatButton.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FloatButton  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FloatButton  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 14 optional)', () => {
    // All 14 optional props omitted — should not crash
    const { container } = render(<FloatButton  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _floatbuttonshape: FloatButtonShape | undefined = undefined; void _floatbuttonshape;
    const _floatbuttonsize: FloatButtonSize | undefined = undefined; void _floatbuttonsize;
    const _floatbuttonposition: FloatButtonPosition | undefined = undefined; void _floatbuttonposition;
    const _floatbuttontrigger: FloatButtonTrigger | undefined = undefined; void _floatbuttontrigger;
    const _floatbuttongroupitem: FloatButtonGroupItem | undefined = undefined; void _floatbuttongroupitem;
    expect(true).toBe(true);
  });
});
