// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ShellHeader } from '../shell-header/ShellHeader';

describe('ShellHeader — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<ShellHeader  />);
    expect(container.firstElementChild).toBeTruthy();
  });
});
