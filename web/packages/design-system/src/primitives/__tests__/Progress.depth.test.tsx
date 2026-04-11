// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Progress } from '../progress/Progress';

afterEach(cleanup);

describe('Progress — depth', () => {
  describe('Progress — depth: prop combinations', () => {
    it('renders with showInfo', () => {
      const { container } = render(<Progress showInfo />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
