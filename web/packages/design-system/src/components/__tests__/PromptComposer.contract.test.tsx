// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PromptComposer } from '../prompt-composer/PromptComposer';
import type { PromptComposerScope, PromptComposerTone, PromptComposerProps, PromptComposerRef } from '../prompt-composer/PromptComposer';

describe('PromptComposer — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<PromptComposer  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(PromptComposer.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<PromptComposer  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<PromptComposer  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 19 optional)', () => {
    // All 19 optional props omitted — should not crash
    const { container } = render(<PromptComposer  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _promptcomposerscope: PromptComposerScope | undefined = undefined; void _promptcomposerscope;
    const _promptcomposertone: PromptComposerTone | undefined = undefined; void _promptcomposertone;
    const _promptcomposerprops: PromptComposerProps | undefined = undefined; void _promptcomposerprops;
    const _promptcomposerref: PromptComposerRef | undefined = undefined; void _promptcomposerref;
    expect(true).toBe(true);
  });
});
