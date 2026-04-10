// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CommentThread } from '../CommentThread';

afterEach(cleanup);

const requiredProps = {
  comments: [],
};
describe('CommentThread — depth', () => {
  describe('CommentThread — depth: comments array edge cases', () => {
    it('handles empty comments', () => {
      const { container } = render(<CommentThread {...requiredProps} comments={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item comments', () => {
      const { container } = render(<CommentThread {...requiredProps} comments={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
