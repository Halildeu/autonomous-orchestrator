// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GanttTimeline } from '../GanttTimeline';

afterEach(cleanup);

const requiredProps = {
  tasks: [],
};
describe('GanttTimeline — depth', () => {
  describe('GanttTimeline — depth: prop combinations', () => {
    it('renders with showDependencies', () => {
      const { container } = render(<GanttTimeline {...requiredProps} showDependencies />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('GanttTimeline — depth: tasks array edge cases', () => {
    it('handles empty tasks', () => {
      const { container } = render(<GanttTimeline {...requiredProps} tasks={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item tasks', () => {
      const { container } = render(<GanttTimeline {...requiredProps} tasks={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
