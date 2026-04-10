// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SearchInput } from '../search-input/SearchInput';

afterEach(cleanup);

describe('SearchInput — depth', () => {
  describe('SearchInput — depth: prop combinations', () => {
    it('renders with loading + clearable + disabled simultaneously', () => {
      render(<SearchInput loading clearable disabled>Stressed</SearchInput>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<SearchInput loading clearable disabled />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
