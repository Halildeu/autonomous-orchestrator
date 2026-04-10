// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ApprovalWorkflow } from '../ApprovalWorkflow';

afterEach(cleanup);

const requiredProps = {
  steps: [],
};
describe('ApprovalWorkflow — depth', () => {
  describe('ApprovalWorkflow — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<ApprovalWorkflow {...requiredProps} compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ApprovalWorkflow — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<ApprovalWorkflow {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ApprovalWorkflow — depth: steps array edge cases', () => {
    it('handles empty steps', () => {
      const { container } = render(<ApprovalWorkflow {...requiredProps} steps={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item steps', () => {
      const { container } = render(<ApprovalWorkflow {...requiredProps} steps={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
