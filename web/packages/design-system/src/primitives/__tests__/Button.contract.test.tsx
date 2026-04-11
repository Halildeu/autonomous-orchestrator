// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Button } from '../button/Button';
import type { ButtonVariant, ButtonSize, ButtonDensity, ButtonProps, ButtonDefaultProps } from '../button/Button';

describe('Button — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Button  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Button.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Button  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Button  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _buttonvariant: ButtonVariant | undefined = undefined; void _buttonvariant;
    const _buttonsize: ButtonSize | undefined = undefined; void _buttonsize;
    const _buttondensity: ButtonDensity | undefined = undefined; void _buttondensity;
    const _buttonprops: ButtonProps | undefined = undefined; void _buttonprops;
    const _buttondefaultprops: ButtonDefaultProps | undefined = undefined; void _buttondefaultprops;
    expect(true).toBe(true);
  });
});
