// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Card } from '../card/Card';
import type { CardVariant, CardPadding, CardSlot, CardProps, CardHeaderProps } from '../card/Card';

describe('Card — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Card  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Card.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<Card  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _cardvariant: CardVariant | undefined = undefined; void _cardvariant;
    const _cardpadding: CardPadding | undefined = undefined; void _cardpadding;
    const _cardslot: CardSlot | undefined = undefined; void _cardslot;
    const _cardprops: CardProps | undefined = undefined; void _cardprops;
    const _cardheaderprops: CardHeaderProps | undefined = undefined; void _cardheaderprops;
    expect(true).toBe(true);
  });
});
