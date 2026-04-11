// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ConfidenceBadge } from '../confidence-badge/ConfidenceBadge';
import type { ConfidenceLevel, ConfidenceBadgeProps } from '../confidence-badge/ConfidenceBadge';

describe('ConfidenceBadge — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ConfidenceBadge  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConfidenceBadge.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ConfidenceBadge  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ConfidenceBadge  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<ConfidenceBadge  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _confidencelevel: ConfidenceLevel | undefined = undefined; void _confidencelevel;
    const _confidencebadgeprops: ConfidenceBadgeProps | undefined = undefined; void _confidencebadgeprops;
    expect(true).toBe(true);
  });
});
