// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Stack } from '../stack/Stack';
import type { StackDirection, StackAlign, StackJustify, StackGap, StackProps } from '../stack/Stack';

describe('Stack — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Stack  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Stack.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<Stack  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _stackdirection: StackDirection | undefined = undefined; void _stackdirection;
    const _stackalign: StackAlign | undefined = undefined; void _stackalign;
    const _stackjustify: StackJustify | undefined = undefined; void _stackjustify;
    const _stackgap: StackGap | undefined = undefined; void _stackgap;
    const _stackprops: StackProps | undefined = undefined; void _stackprops;
    expect(true).toBe(true);
  });
});
