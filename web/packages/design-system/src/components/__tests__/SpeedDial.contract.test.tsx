// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SpeedDial } from '../speed-dial/SpeedDial';
import type { SpeedDialDirection, SpeedDialAction, SpeedDialProps } from '../speed-dial/SpeedDial';

describe('SpeedDial — contract', () => {
  const defaultProps = {
    actions: [],
  };

  it('renders without crash', () => {
    const { container } = render(<SpeedDial {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SpeedDial.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<SpeedDial {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _speeddialdirection: SpeedDialDirection | undefined = undefined; void _speeddialdirection;
    const _speeddialaction: SpeedDialAction | undefined = undefined; void _speeddialaction;
    const _speeddialprops: SpeedDialProps | undefined = undefined; void _speeddialprops;
    expect(true).toBe(true);
  });
});
