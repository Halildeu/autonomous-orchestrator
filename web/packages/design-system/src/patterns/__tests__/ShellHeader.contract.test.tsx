// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ShellHeader } from '../shell-header/ShellHeader';

describe('ShellHeader — contract', () => {
  const defaultProps = {
    navItems: [],
    onNavigate: vi.fn(),
  };

  it('renders without crash', () => {
    const { container } = render(<ShellHeader {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });
});
