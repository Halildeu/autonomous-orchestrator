// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Accordion } from '../accordion/Accordion';
import type { AccordionSelectionMode, AccordionSize, AccordionExpandIconPosition, AccordionCollapsible, AccordionSectionInput } from '../accordion/Accordion';

describe('Accordion — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Accordion {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Accordion.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Accordion {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Accordion {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 18 optional)', () => {
    // All 18 optional props omitted — should not crash
    const { container } = render(<Accordion {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _accordionselectionmode: AccordionSelectionMode | undefined = undefined; void _accordionselectionmode;
    const _accordionsize: AccordionSize | undefined = undefined; void _accordionsize;
    const _accordionexpandiconposition: AccordionExpandIconPosition | undefined = undefined; void _accordionexpandiconposition;
    const _accordioncollapsible: AccordionCollapsible | undefined = undefined; void _accordioncollapsible;
    const _accordionsectioninput: AccordionSectionInput | undefined = undefined; void _accordionsectioninput;
    expect(true).toBe(true);
  });
});
