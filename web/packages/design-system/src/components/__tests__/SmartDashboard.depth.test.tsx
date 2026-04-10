// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SmartDashboard } from '../smart-dashboard/SmartDashboard';

afterEach(cleanup);

const requiredProps = {
  widgets: [],
};
describe('SmartDashboard — depth', () => {
  describe('SmartDashboard — depth: columns variants', () => {
    it.each(['2', '3', '4'] as const)('columns=%s renders without crash', (val) => {
      const { container } = render(<SmartDashboard {...requiredProps} columns={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SmartDashboard — depth: widgets array edge cases', () => {
    it('handles empty widgets', () => {
      const { container } = render(<SmartDashboard {...requiredProps} widgets={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item widgets', () => {
      const { container } = render(<SmartDashboard {...requiredProps} widgets={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SmartDashboard — depth: onWidgetReorder array edge cases', () => {
    it('handles empty onWidgetReorder', () => {
      const { container } = render(<SmartDashboard {...requiredProps} onWidgetReorder={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onWidgetReorder', () => {
      const { container } = render(<SmartDashboard {...requiredProps} onWidgetReorder={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
