// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ConnectedRadio } from '../connected/ConnectedRadio';
import type { ConnectedRadioProps, ConnectedRadioRef, ConnectedRadioElement, ConnectedRadioCSSProperties } from '../connected/ConnectedRadio';

describe('ConnectedRadio — contract', () => {
  const defaultProps = {
    name: 'test',
    radioValue: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<ConnectedRadio {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConnectedRadio.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<ConnectedRadio {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _connectedradioprops: ConnectedRadioProps | undefined = undefined; void _connectedradioprops;
    const _connectedradioref: ConnectedRadioRef | undefined = undefined; void _connectedradioref;
    const _connectedradioelement: ConnectedRadioElement | undefined = undefined; void _connectedradioelement;
    const _connectedradiocssproperties: ConnectedRadioCSSProperties | undefined = undefined; void _connectedradiocssproperties;
    expect(true).toBe(true);
  });
});
