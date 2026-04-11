// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { HoverDescription } from '../hover-description/HoverDescription';
import type { HoverDescriptionProps } from '../hover-description/HoverDescription';

describe('HoverDescription — contract', () => {
  const defaultProps = {
    description: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<HoverDescription {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(HoverDescription.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<HoverDescription {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _hoverdescriptionprops: HoverDescriptionProps | undefined = undefined; void _hoverdescriptionprops;
    expect(true).toBe(true);
  });
});
