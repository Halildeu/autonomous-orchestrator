// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Text } from '../text/Text';
import type { TextVariant, TextSize, TextWeight, TextProps } from '../text/Text';

describe('Text — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Text  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Text.displayName).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _textvariant: TextVariant | undefined = undefined; void _textvariant;
    const _textsize: TextSize | undefined = undefined; void _textsize;
    const _textweight: TextWeight | undefined = undefined; void _textweight;
    const _textprops: TextProps | undefined = undefined; void _textprops;
    expect(true).toBe(true);
  });
});
