// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Slot } from '../_shared/Slot';

afterEach(cleanup);

describe('Slot — depth', () => {
  describe('Slot — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Slot>{null}</Slot>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Slot>{0}</Slot>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Slot>{''}</Slot>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
