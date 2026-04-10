// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ApprovalCheckpoint } from '../approval-checkpoint/ApprovalCheckpoint';

afterEach(cleanup);

const requiredProps = {
  title: 'content',
  summary: 'content',
};
describe('ApprovalCheckpoint — depth', () => {
  describe('ApprovalCheckpoint — depth: evidenceItems array edge cases', () => {
    it('handles empty evidenceItems', () => {
      const { container } = render(<ApprovalCheckpoint {...requiredProps} evidenceItems={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item evidenceItems', () => {
      const { container } = render(<ApprovalCheckpoint {...requiredProps} evidenceItems={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ApprovalCheckpoint — depth: steps array edge cases', () => {
    it('handles empty steps', () => {
      const { container } = render(<ApprovalCheckpoint {...requiredProps} steps={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item steps', () => {
      const { container } = render(<ApprovalCheckpoint {...requiredProps} steps={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
