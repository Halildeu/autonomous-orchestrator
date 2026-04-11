// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Flex } from '../flex/Flex';
import type { FlexDirection, FlexAlign, FlexJustify, FlexWrap, FlexGap } from '../flex/Flex';

describe('Flex — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Flex  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Flex.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<Flex  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _flexdirection: FlexDirection | undefined = undefined; void _flexdirection;
    const _flexalign: FlexAlign | undefined = undefined; void _flexalign;
    const _flexjustify: FlexJustify | undefined = undefined; void _flexjustify;
    const _flexwrap: FlexWrap | undefined = undefined; void _flexwrap;
    const _flexgap: FlexGap | undefined = undefined; void _flexgap;
    expect(true).toBe(true);
  });
});
