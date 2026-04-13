// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Transition } from '../Transition';
import type { TransitionProps, TransitionRef, TransitionElement, TransitionCSSProperties } from '../Transition';

describe('Transition — contract', () => {
  const defaultProps = {
    show: true,
  };

  it('renders without crash', () => {
    const { container } = render(<Transition {...defaultProps}><div>child</div></Transition>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Transition.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 7 optional)', () => {
    // Transition requires children to render anything visible
    const { container } = render(<Transition {...defaultProps}><div>child</div></Transition>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _transitionprops: TransitionProps | undefined = undefined; void _transitionprops;
    const _transitionref: TransitionRef | undefined = undefined; void _transitionref;
    const _transitionelement: TransitionElement | undefined = undefined; void _transitionelement;
    const _transitioncssproperties: TransitionCSSProperties | undefined = undefined; void _transitioncssproperties;
    expect(true).toBe(true);
  });
});
