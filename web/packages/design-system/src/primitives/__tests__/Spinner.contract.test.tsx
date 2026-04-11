// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Spinner } from '../spinner/Spinner';
import type { SpinnerSize, SpinnerMode, SpinnerProps } from '../spinner/Spinner';

describe('Spinner — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Spinner  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Spinner.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<Spinner  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _spinnersize: SpinnerSize | undefined = undefined; void _spinnersize;
    const _spinnermode: SpinnerMode | undefined = undefined; void _spinnermode;
    const _spinnerprops: SpinnerProps | undefined = undefined; void _spinnerprops;
    expect(true).toBe(true);
  });
});
