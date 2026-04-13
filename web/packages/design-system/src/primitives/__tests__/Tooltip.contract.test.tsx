// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Tooltip } from '../tooltip/Tooltip';
import type { TooltipPlacement, TooltipAlign, TooltipProps } from '../tooltip/Tooltip';

describe('Tooltip — contract', () => {

  it('renders without crash', () => {
    const { container } = render(<Tooltip content="tip"><span>trigger</span></Tooltip>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Tooltip.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // Tooltip requires children to render anything visible
    const { container } = render(<Tooltip><span>trigger</span></Tooltip>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _tooltipplacement: TooltipPlacement | undefined = undefined; void _tooltipplacement;
    const _tooltipalign: TooltipAlign | undefined = undefined; void _tooltipalign;
    const _tooltipprops: TooltipProps | undefined = undefined; void _tooltipprops;
    expect(true).toBe(true);
  });
});
