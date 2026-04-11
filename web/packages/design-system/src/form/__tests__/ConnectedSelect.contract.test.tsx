// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ConnectedSelect } from '../connected/ConnectedSelect';
import type { ConnectedSelectProps, ConnectedSelectRef, ConnectedSelectElement, ConnectedSelectCSSProperties } from '../connected/ConnectedSelect';

describe('ConnectedSelect — contract', () => {
  const defaultProps = {
    name: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<ConnectedSelect {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConnectedSelect.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<ConnectedSelect {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _connectedselectprops: ConnectedSelectProps | undefined = undefined; void _connectedselectprops;
    const _connectedselectref: ConnectedSelectRef | undefined = undefined; void _connectedselectref;
    const _connectedselectelement: ConnectedSelectElement | undefined = undefined; void _connectedselectelement;
    const _connectedselectcssproperties: ConnectedSelectCSSProperties | undefined = undefined; void _connectedselectcssproperties;
    expect(true).toBe(true);
  });
});
