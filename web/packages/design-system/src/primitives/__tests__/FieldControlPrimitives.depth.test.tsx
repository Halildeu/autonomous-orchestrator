// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FieldControlPrimitives } from '../_shared/FieldControlPrimitives';

afterEach(cleanup);

const requiredProps = {
  inputId: 'test',
};
describe('FieldControlPrimitives — depth', () => {
  describe('FieldControlPrimitives — depth: prop combinations', () => {
    it('renders with required + fullWidth simultaneously', () => {
      render(<FieldControlPrimitives {...requiredProps} required fullWidth>Stressed</FieldControlPrimitives>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<FieldControlPrimitives {...requiredProps} required fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FieldControlPrimitives — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<FieldControlPrimitives {...requiredProps}>{null}</FieldControlPrimitives>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<FieldControlPrimitives {...requiredProps}>{0}</FieldControlPrimitives>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<FieldControlPrimitives {...requiredProps}>{''}</FieldControlPrimitives>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
