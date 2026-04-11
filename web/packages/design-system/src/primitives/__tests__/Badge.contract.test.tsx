// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Badge } from '../badge/Badge';
import type { BadgeVariant, BadgeSize, BadgeProps } from '../badge/Badge';

describe('Badge — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Badge  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Badge.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<Badge  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _badgevariant: BadgeVariant | undefined = undefined; void _badgevariant;
    const _badgesize: BadgeSize | undefined = undefined; void _badgesize;
    const _badgeprops: BadgeProps | undefined = undefined; void _badgeprops;
    expect(true).toBe(true);
  });
});
