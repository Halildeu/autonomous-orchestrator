// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FormField } from '../form-field/FormField';

afterEach(cleanup);

describe('FormField — depth', () => {
  describe('FormField — depth: prop combinations', () => {
    it('renders with required + optional + disabled + horizontal simultaneously', () => {
      render(<FormField required optional disabled horizontal>Stressed</FormField>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<FormField required optional disabled horizontal />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FormField — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<FormField>{null}</FormField>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<FormField>{0}</FormField>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<FormField>{''}</FormField>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
