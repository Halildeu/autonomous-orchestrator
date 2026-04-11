// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FineKinney } from '../FineKinney';
import type { FineKinneyProbability, FineKinneyFrequency, FineKinneySeverity, FineKinneyRisk, FineKinneyLocaleText } from '../FineKinney';

describe('FineKinney — contract', () => {
  const defaultProps = {
    risks: [],
  };

  it('renders without crash', () => {
    const { container } = render(<FineKinney {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FineKinney.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FineKinney {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FineKinney {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<FineKinney {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _finekinneyprobability: FineKinneyProbability | undefined = undefined; void _finekinneyprobability;
    const _finekinneyfrequency: FineKinneyFrequency | undefined = undefined; void _finekinneyfrequency;
    const _finekinneyseverity: FineKinneySeverity | undefined = undefined; void _finekinneyseverity;
    const _finekinneyrisk: FineKinneyRisk | undefined = undefined; void _finekinneyrisk;
    const _finekinneylocaletext: FineKinneyLocaleText | undefined = undefined; void _finekinneylocaletext;
    expect(true).toBe(true);
  });
});
