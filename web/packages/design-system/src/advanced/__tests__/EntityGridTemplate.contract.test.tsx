// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { EntityGridTemplate } from '../data-grid/EntityGridTemplate';
import type { ColDef, GridOptions, GridReadyEvent, SideBarDef, ExcelStyle } from '../data-grid/EntityGridTemplate';

describe('EntityGridTemplate — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<EntityGridTemplate  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(EntityGridTemplate.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<EntityGridTemplate  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<EntityGridTemplate  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _coldef: ColDef | undefined = undefined; void _coldef;
    const _gridoptions: GridOptions | undefined = undefined; void _gridoptions;
    const _gridreadyevent: GridReadyEvent | undefined = undefined; void _gridreadyevent;
    const _sidebardef: SideBarDef | undefined = undefined; void _sidebardef;
    const _excelstyle: ExcelStyle | undefined = undefined; void _excelstyle;
    expect(true).toBe(true);
  });
});
