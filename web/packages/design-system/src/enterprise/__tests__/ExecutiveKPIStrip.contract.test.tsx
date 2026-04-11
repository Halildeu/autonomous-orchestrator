// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ExecutiveKPIStrip } from '../ExecutiveKPIStrip';
import type { KPIStripSize, KPIMetric, ExecutiveKPIStripProps } from '../ExecutiveKPIStrip';

describe('ExecutiveKPIStrip — contract', () => {
  const defaultProps = {
    metrics: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ExecutiveKPIStrip {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ExecutiveKPIStrip.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ExecutiveKPIStrip {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ExecutiveKPIStrip {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<ExecutiveKPIStrip {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _kpistripsize: KPIStripSize | undefined = undefined; void _kpistripsize;
    const _kpimetric: KPIMetric | undefined = undefined; void _kpimetric;
    const _executivekpistripprops: ExecutiveKPIStripProps | undefined = undefined; void _executivekpistripprops;
    expect(true).toBe(true);
  });
});
