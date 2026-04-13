// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AnimatePresence } from '../AnimatePresence';
import type { AnimatePresenceProps, AnimatePresenceRef, AnimatePresenceElement, AnimatePresenceCSSProperties } from '../AnimatePresence';

describe('AnimatePresence — contract', () => {

  it('renders without crash', () => {
    const { container } = render(<AnimatePresence><div>child</div></AnimatePresence>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AnimatePresence.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // AnimatePresence requires children to render anything visible
    const { container } = render(<AnimatePresence><div>child</div></AnimatePresence>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _animatepresenceprops: AnimatePresenceProps | undefined = undefined; void _animatepresenceprops;
    const _animatepresenceref: AnimatePresenceRef | undefined = undefined; void _animatepresenceref;
    const _animatepresenceelement: AnimatePresenceElement | undefined = undefined; void _animatepresenceelement;
    const _animatepresencecssproperties: AnimatePresenceCSSProperties | undefined = undefined; void _animatepresencecssproperties;
    expect(true).toBe(true);
  });
});
