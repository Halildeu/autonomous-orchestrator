// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Container } from '../container/Container';
import type { ContainerMaxWidth, ContainerProps } from '../container/Container';

describe('Container — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Container  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Container.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<Container  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _containermaxwidth: ContainerMaxWidth | undefined = undefined; void _containermaxwidth;
    const _containerprops: ContainerProps | undefined = undefined; void _containerprops;
    expect(true).toBe(true);
  });
});
