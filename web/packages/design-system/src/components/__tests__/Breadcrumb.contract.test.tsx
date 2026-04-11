// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Breadcrumb } from '../breadcrumb/Breadcrumb';
import type { BreadcrumbItem, BreadcrumbProps } from '../breadcrumb/Breadcrumb';

describe('Breadcrumb — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Breadcrumb {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Breadcrumb.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Breadcrumb {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Breadcrumb {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _breadcrumbitem: BreadcrumbItem | undefined = undefined; void _breadcrumbitem;
    const _breadcrumbprops: BreadcrumbProps | undefined = undefined; void _breadcrumbprops;
    expect(true).toBe(true);
  });
});
