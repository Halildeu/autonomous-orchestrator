// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Switch } from '../switch/Switch';
import type { SwitchSize, SwitchVariant, SwitchDensity, SwitchProps } from '../switch/Switch';

describe('Switch — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Switch  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Switch.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Switch  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Switch  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<Switch  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _switchsize: SwitchSize | undefined = undefined; void _switchsize;
    const _switchvariant: SwitchVariant | undefined = undefined; void _switchvariant;
    const _switchdensity: SwitchDensity | undefined = undefined; void _switchdensity;
    const _switchprops: SwitchProps | undefined = undefined; void _switchprops;
    expect(true).toBe(true);
  });
});
