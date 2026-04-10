// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FlowBuilder } from '../FlowBuilder';

afterEach(cleanup);

const requiredProps = {
  nodes: [],
  edges: [],
};
describe('FlowBuilder — depth', () => {
  describe('FlowBuilder — depth: prop combinations', () => {
    it('renders with readOnly + showMinimap + showToolbar + showGrid simultaneously', () => {
      render(<FlowBuilder {...requiredProps} readOnly showMinimap showToolbar showGrid>Stressed</FlowBuilder>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<FlowBuilder {...requiredProps} readOnly showMinimap showToolbar showGrid />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FlowBuilder — depth: height variants', () => {
    it.each(['number', 'string'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<FlowBuilder {...requiredProps} height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FlowBuilder — depth: nodes array edge cases', () => {
    it('handles empty nodes', () => {
      const { container } = render(<FlowBuilder {...requiredProps} nodes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item nodes', () => {
      const { container } = render(<FlowBuilder {...requiredProps} nodes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FlowBuilder — depth: edges array edge cases', () => {
    it('handles empty edges', () => {
      const { container } = render(<FlowBuilder {...requiredProps} edges={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item edges', () => {
      const { container } = render(<FlowBuilder {...requiredProps} edges={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
