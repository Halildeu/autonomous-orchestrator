// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Dropdown } from '../dropdown/Dropdown';
import type { DropdownItem, DropdownSeparator, DropdownLabel, DropdownEntry, DropdownPlacement } from '../dropdown/Dropdown';

describe('Dropdown — contract', () => {
  const defaultProps = {
    items: [] as DropdownEntry[],
  };

  it('renders without crash', () => {
    // Dropdown requires a child element as the trigger
    const { container } = render(<Dropdown {...defaultProps}><button>trigger</button></Dropdown>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Dropdown.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 4 optional)', () => {
    const { container } = render(<Dropdown {...defaultProps}><button>trigger</button></Dropdown>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _dropdownitem: DropdownItem | undefined = undefined; void _dropdownitem;
    const _dropdownseparator: DropdownSeparator | undefined = undefined; void _dropdownseparator;
    const _dropdownlabel: DropdownLabel | undefined = undefined; void _dropdownlabel;
    const _dropdownentry: DropdownEntry | undefined = undefined; void _dropdownentry;
    const _dropdownplacement: DropdownPlacement | undefined = undefined; void _dropdownplacement;
    expect(true).toBe(true);
  });
});
