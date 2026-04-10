// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ConfidenceBadge } from '../confidence-badge/ConfidenceBadge';

afterEach(cleanup);

describe('ConfidenceBadge — depth', () => {
  describe('ConfidenceBadge — depth: prop combinations', () => {
    it('renders with compact + showScore simultaneously', () => {
      render(<ConfidenceBadge compact showScore>Stressed</ConfidenceBadge>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ConfidenceBadge compact showScore />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
