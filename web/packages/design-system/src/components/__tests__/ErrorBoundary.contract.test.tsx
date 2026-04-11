// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ErrorBoundary } from '../error-boundary/ErrorBoundary';
import type { ErrorBoundaryFallback, ErrorBoundaryProps, ErrorBoundaryComponentProps, ErrorBoundaryFallbackType } from '../error-boundary/ErrorBoundary';

describe('ErrorBoundary — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ErrorBoundary  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ErrorBoundary.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ErrorBoundary  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ErrorBoundary  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _errorboundaryfallback: ErrorBoundaryFallback | undefined = undefined; void _errorboundaryfallback;
    const _errorboundaryprops: ErrorBoundaryProps | undefined = undefined; void _errorboundaryprops;
    const _errorboundarycomponentprops: ErrorBoundaryComponentProps | undefined = undefined; void _errorboundarycomponentprops;
    const _errorboundaryfallbacktype: ErrorBoundaryFallbackType | undefined = undefined; void _errorboundaryfallbacktype;
    expect(true).toBe(true);
  });
});
