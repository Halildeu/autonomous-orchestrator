// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { BottomNavigation } from '../bottom-navigation/BottomNavigation';
import type { BottomNavigationProps, BottomNavigationItemProps } from '../bottom-navigation/BottomNavigation';

describe('BottomNavigation — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<BottomNavigation  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(BottomNavigation.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<BottomNavigation  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _bottomnavigationprops: BottomNavigationProps | undefined = undefined; void _bottomnavigationprops;
    const _bottomnavigationitemprops: BottomNavigationItemProps | undefined = undefined; void _bottomnavigationitemprops;
    expect(true).toBe(true);
  });
});
