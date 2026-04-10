// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { PromptComposer } from '../prompt-composer/PromptComposer';

afterEach(cleanup);

describe('PromptComposer — depth', () => {
  describe('PromptComposer — depth: guardrails array edge cases', () => {
    it('handles empty guardrails', () => {
      const { container } = render(<PromptComposer guardrails={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item guardrails', () => {
      const { container } = render(<PromptComposer guardrails={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('PromptComposer — depth: citations array edge cases', () => {
    it('handles empty citations', () => {
      const { container } = render(<PromptComposer citations={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item citations', () => {
      const { container } = render(<PromptComposer citations={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('PromptComposer — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<PromptComposer value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<PromptComposer defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
