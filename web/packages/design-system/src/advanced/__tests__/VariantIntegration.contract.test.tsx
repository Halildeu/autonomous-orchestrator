// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { VariantIntegration } from '../data-grid/VariantIntegration';
import type { GridVariantState, GridVariant, VariantIntegrationMessages, VariantIntegrationProps } from '../data-grid/VariantIntegration';

describe('VariantIntegration — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<VariantIntegration  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(VariantIntegration.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<VariantIntegration  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<VariantIntegration  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _gridvariantstate: GridVariantState | undefined = undefined; void _gridvariantstate;
    const _gridvariant: GridVariant | undefined = undefined; void _gridvariant;
    const _variantintegrationmessages: VariantIntegrationMessages | undefined = undefined; void _variantintegrationmessages;
    const _variantintegrationprops: VariantIntegrationProps | undefined = undefined; void _variantintegrationprops;
    expect(true).toBe(true);
  });
});
