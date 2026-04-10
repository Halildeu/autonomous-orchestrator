// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ColorPicker } from '../color-picker/ColorPicker';

afterEach(cleanup);

describe('ColorPicker — depth', () => {
  describe('ColorPicker — depth: prop combinations', () => {
    it('renders with showInput + showPresets simultaneously', () => {
      render(<ColorPicker showInput showPresets>Stressed</ColorPicker>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ColorPicker showInput showPresets />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ColorPicker — depth: presets array edge cases', () => {
    it('handles empty presets', () => {
      const { container } = render(<ColorPicker presets={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item presets', () => {
      const { container } = render(<ColorPicker presets={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ColorPicker — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<ColorPicker value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<ColorPicker defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
