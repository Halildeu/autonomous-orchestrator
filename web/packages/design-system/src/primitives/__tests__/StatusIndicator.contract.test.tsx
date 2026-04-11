// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { StatusIndicator } from '../status-indicator/StatusIndicator';
import type { StatusIndicatorStatus, StatusIndicatorSize, StatusIndicatorProps } from '../status-indicator/StatusIndicator';

describe('StatusIndicator — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<StatusIndicator  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<StatusIndicator  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _statusindicatorstatus: StatusIndicatorStatus | undefined = undefined; void _statusindicatorstatus;
    const _statusindicatorsize: StatusIndicatorSize | undefined = undefined; void _statusindicatorsize;
    const _statusindicatorprops: StatusIndicatorProps | undefined = undefined; void _statusindicatorprops;
    expect(true).toBe(true);
  });
});
