// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CommandPaletteTrigger } from '../command-palette-trigger/CommandPaletteTrigger';

afterEach(cleanup);

describe('CommandPaletteTrigger — depth', () => {
  describe('CommandPaletteTrigger — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<CommandPaletteTrigger compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
