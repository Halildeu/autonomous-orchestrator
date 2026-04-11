// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { CommandPaletteTrigger } from '../command-palette-trigger/CommandPaletteTrigger';
import type { CommandPaletteTriggerProps } from '../command-palette-trigger/CommandPaletteTrigger';

describe('CommandPaletteTrigger — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<CommandPaletteTrigger  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<CommandPaletteTrigger  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _commandpalettetriggerprops: CommandPaletteTriggerProps | undefined = undefined; void _commandpalettetriggerprops;
    expect(true).toBe(true);
  });
});
