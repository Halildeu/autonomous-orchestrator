// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AILayoutBuilder } from '../ai-layout-builder/AILayoutBuilder';

afterEach(cleanup);

const requiredProps = {
  blocks: [],
};
describe('AILayoutBuilder — depth', () => {
  describe('AILayoutBuilder — depth: prop combinations', () => {
    it('renders with draggable', () => {
      const { container } = render(<AILayoutBuilder {...requiredProps} draggable />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AILayoutBuilder — depth: columns variants', () => {
    it.each(['1', '2', '3', '4'] as const)('columns=%s renders without crash', (val) => {
      const { container } = render(<AILayoutBuilder {...requiredProps} columns={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AILayoutBuilder — depth: blocks array edge cases', () => {
    it('handles empty blocks', () => {
      const { container } = render(<AILayoutBuilder {...requiredProps} blocks={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item blocks', () => {
      const { container } = render(<AILayoutBuilder {...requiredProps} blocks={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AILayoutBuilder — depth: onBlockReorder array edge cases', () => {
    it('handles empty onBlockReorder', () => {
      const { container } = render(<AILayoutBuilder {...requiredProps} onBlockReorder={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onBlockReorder', () => {
      const { container } = render(<AILayoutBuilder {...requiredProps} onBlockReorder={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
