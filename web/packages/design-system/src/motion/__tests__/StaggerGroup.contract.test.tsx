// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { StaggerGroup } from '../StaggerGroup';
import type { StaggerGroupProps, StaggerGroupRef, StaggerGroupElement, StaggerGroupCSSProperties } from '../StaggerGroup';

describe('StaggerGroup — contract', () => {

  it('renders without crash', () => {
    const { container } = render(<StaggerGroup><div>child</div></StaggerGroup>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(StaggerGroup.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // StaggerGroup requires children to render anything visible
    const { container } = render(<StaggerGroup><div>child</div></StaggerGroup>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _staggergroupprops: StaggerGroupProps | undefined = undefined; void _staggergroupprops;
    const _staggergroupref: StaggerGroupRef | undefined = undefined; void _staggergroupref;
    const _staggergroupelement: StaggerGroupElement | undefined = undefined; void _staggergroupelement;
    const _staggergroupcssproperties: StaggerGroupCSSProperties | undefined = undefined; void _staggergroupcssproperties;
    expect(true).toBe(true);
  });
});
