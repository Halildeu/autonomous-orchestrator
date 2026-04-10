// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FilterPresets } from '../FilterPresets';

afterEach(cleanup);

const requiredProps = {
  presets: [],
  onSelect: vi.fn(),
};
describe('FilterPresets — depth', () => {
  describe('FilterPresets — depth: presets array edge cases', () => {
    it('handles empty presets', () => {
      const { container } = render(<FilterPresets {...requiredProps} presets={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item presets', () => {
      const { container } = render(<FilterPresets {...requiredProps} presets={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
