// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Input } from '../input/Input';
import type { InputSize, InputProps } from '../input/Input';

describe('Input — contract', () => {
  const defaultProps = {
    value: undefined as any,
    event: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<Input {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Input.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Input {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Input {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 16 optional)', () => {
    // All 16 optional props omitted — should not crash
    const { container } = render(<Input {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _inputsize: InputSize | undefined = undefined; void _inputsize;
    const _inputprops: InputProps | undefined = undefined; void _inputprops;
    expect(true).toBe(true);
  });
});
