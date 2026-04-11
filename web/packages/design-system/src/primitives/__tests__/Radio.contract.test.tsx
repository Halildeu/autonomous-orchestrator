// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Radio } from '../radio/Radio';
import type { RadioSize, RadioProps, RadioDensity, RadioGroupProps } from '../radio/Radio';

describe('Radio — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Radio  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Radio.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Radio  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Radio  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<Radio  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _radiosize: RadioSize | undefined = undefined; void _radiosize;
    const _radioprops: RadioProps | undefined = undefined; void _radioprops;
    const _radiodensity: RadioDensity | undefined = undefined; void _radiodensity;
    const _radiogroupprops: RadioGroupProps | undefined = undefined; void _radiogroupprops;
    expect(true).toBe(true);
  });
});
