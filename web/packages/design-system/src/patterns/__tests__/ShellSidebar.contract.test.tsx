// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ShellSidebar } from '../shell-sidebar/ShellSidebar';

describe('ShellSidebar — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ShellSidebar  />);
    expect(container.firstElementChild).toBeTruthy();
  });
});
