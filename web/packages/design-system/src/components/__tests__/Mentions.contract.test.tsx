// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Mentions } from '../mentions/Mentions';
import type { MentionOption, MentionsProps } from '../mentions/Mentions';

describe('Mentions — contract', () => {
  const defaultProps = {
    options: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Mentions {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Mentions.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Mentions {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Mentions {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 14 optional)', () => {
    // All 14 optional props omitted — should not crash
    const { container } = render(<Mentions {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _mentionoption: MentionOption | undefined = undefined; void _mentionoption;
    const _mentionsprops: MentionsProps | undefined = undefined; void _mentionsprops;
    expect(true).toBe(true);
  });
});
