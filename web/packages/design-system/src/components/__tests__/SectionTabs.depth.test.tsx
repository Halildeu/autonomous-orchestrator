// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SectionTabs } from '../detail-section-tabs/SectionTabs';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('SectionTabs — depth', () => {
  describe('SectionTabs — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<SectionTabs {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<SectionTabs {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SectionTabs — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<SectionTabs {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<SectionTabs {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
