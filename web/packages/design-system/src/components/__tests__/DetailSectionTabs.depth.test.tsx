// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DetailSectionTabs } from '../detail-section-tabs/DetailSectionTabs';

afterEach(cleanup);

const requiredProps = {
  tabs: [],
  activeTabId: 'test',
  onTabChange: vi.fn(),
};
describe('DetailSectionTabs — depth', () => {
  describe('DetailSectionTabs — depth: prop combinations', () => {
    it('renders with sticky', () => {
      const { container } = render(<DetailSectionTabs {...requiredProps} sticky />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('DetailSectionTabs — depth: tabs array edge cases', () => {
    it('handles empty tabs', () => {
      const { container } = render(<DetailSectionTabs {...requiredProps} tabs={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item tabs', () => {
      const { container } = render(<DetailSectionTabs {...requiredProps} tabs={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
