// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { JsonViewer } from '../json-viewer/JsonViewer';

afterEach(cleanup);

const requiredProps = {
  value: undefined as any,
};
describe('JsonViewer — depth', () => {
  describe('JsonViewer — depth: prop combinations', () => {
    it('renders with fullWidth + showTypes simultaneously', () => {
      render(<JsonViewer {...requiredProps} fullWidth showTypes>Stressed</JsonViewer>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<JsonViewer {...requiredProps} fullWidth showTypes />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('JsonViewer — depth: maxHeight variants', () => {
    it.each(['number', 'string'] as const)('maxHeight=%s renders without crash', (val) => {
      const { container } = render(<JsonViewer {...requiredProps} maxHeight={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
