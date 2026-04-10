// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QRCode } from '../qr-code/QRCode';

afterEach(cleanup);

const requiredProps = {
  value: 'test',
};
describe('QRCode — depth', () => {
  describe('QRCode — depth: prop combinations', () => {
    it('renders with bordered', () => {
      const { container } = render(<QRCode {...requiredProps} bordered />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('QRCode — depth: status variants', () => {
    it.each(['active', 'expired', 'loading'] as const)('status=%s renders without crash', (val) => {
      const { container } = render(<QRCode {...requiredProps} status={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
