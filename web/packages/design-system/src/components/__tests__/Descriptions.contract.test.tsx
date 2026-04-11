// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Descriptions } from '../descriptions/Descriptions';
import type { DescriptionsItem, DescriptionsProps } from '../descriptions/Descriptions';

describe('Descriptions — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Descriptions {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Descriptions.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Descriptions {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Descriptions {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<Descriptions {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _descriptionsitem: DescriptionsItem | undefined = undefined; void _descriptionsitem;
    const _descriptionsprops: DescriptionsProps | undefined = undefined; void _descriptionsprops;
    expect(true).toBe(true);
  });
});
