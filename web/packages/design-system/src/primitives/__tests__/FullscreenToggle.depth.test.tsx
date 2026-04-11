// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FullscreenToggle } from '../fullscreen-toggle/FullscreenToggle';

afterEach(cleanup);

describe('FullscreenToggle — depth', () => {
  describe('FullscreenToggle — depth: prop combinations', () => {
    it('renders with showLabel', () => {
      const { container } = render(<FullscreenToggle showLabel />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
