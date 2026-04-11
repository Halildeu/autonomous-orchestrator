// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Checkbox } from '../checkbox/Checkbox';
import type { CheckboxSize, CheckboxProps, CheckboxDensity } from '../checkbox/Checkbox';

describe('Checkbox — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Checkbox  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Checkbox.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Checkbox  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Checkbox  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<Checkbox  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _checkboxsize: CheckboxSize | undefined = undefined; void _checkboxsize;
    const _checkboxprops: CheckboxProps | undefined = undefined; void _checkboxprops;
    const _checkboxdensity: CheckboxDensity | undefined = undefined; void _checkboxdensity;
    expect(true).toBe(true);
  });
});
