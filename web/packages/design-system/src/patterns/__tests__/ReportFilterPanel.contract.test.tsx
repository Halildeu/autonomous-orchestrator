// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ReportFilterPanel } from '../report-filter-panel/ReportFilterPanel';
import type { ReportFilterPanelProps, ReportFilterPanelRef, ReportFilterPanelElement, ReportFilterPanelCSSProperties } from '../report-filter-panel/ReportFilterPanel';

describe('ReportFilterPanel — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ReportFilterPanel  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ReportFilterPanel.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ReportFilterPanel  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ReportFilterPanel  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<ReportFilterPanel  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _reportfilterpanelprops: ReportFilterPanelProps | undefined = undefined; void _reportfilterpanelprops;
    const _reportfilterpanelref: ReportFilterPanelRef | undefined = undefined; void _reportfilterpanelref;
    const _reportfilterpanelelement: ReportFilterPanelElement | undefined = undefined; void _reportfilterpanelelement;
    const _reportfilterpanelcssproperties: ReportFilterPanelCSSProperties | undefined = undefined; void _reportfilterpanelcssproperties;
    expect(true).toBe(true);
  });
});
