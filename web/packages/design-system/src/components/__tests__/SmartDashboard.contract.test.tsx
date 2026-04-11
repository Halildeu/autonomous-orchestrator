// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SmartDashboard } from '../smart-dashboard/SmartDashboard';
import type { TrendDirection, WidgetTrend, WidgetType, WidgetTone, WidgetSize } from '../smart-dashboard/SmartDashboard';

describe('SmartDashboard — contract', () => {
  const defaultProps = {
    widgets: [],
  };

  it('renders without crash', () => {
    const { container } = render(<SmartDashboard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SmartDashboard.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<SmartDashboard {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<SmartDashboard {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<SmartDashboard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _trenddirection: TrendDirection | undefined = undefined; void _trenddirection;
    const _widgettrend: WidgetTrend | undefined = undefined; void _widgettrend;
    const _widgettype: WidgetType | undefined = undefined; void _widgettype;
    const _widgettone: WidgetTone | undefined = undefined; void _widgettone;
    const _widgetsize: WidgetSize | undefined = undefined; void _widgetsize;
    expect(true).toBe(true);
  });
});
