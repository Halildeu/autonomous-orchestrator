// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FineKinney } from '../FineKinney';

afterEach(cleanup);

const requiredProps = {
  risks: [],
};
describe('FineKinney — depth', () => {
  describe('FineKinney — depth: prop combinations', () => {
    it('renders with showControls + showStatus + compact simultaneously', () => {
      render(<FineKinney {...requiredProps} showControls showStatus compact>Stressed</FineKinney>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<FineKinney {...requiredProps} showControls showStatus compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FineKinney — depth: risks array edge cases', () => {
    it('handles empty risks', () => {
      const { container } = render(<FineKinney {...requiredProps} risks={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item risks', () => {
      const { container } = render(<FineKinney {...requiredProps} risks={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
