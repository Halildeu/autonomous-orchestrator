// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { GanttTimeline } from '../GanttTimeline';
import type { GanttTask, GanttViewMode, GanttTimelineProps } from '../GanttTimeline';

describe('GanttTimeline — contract', () => {
  const defaultProps = {
    tasks: [],
  };

  it('renders without crash', () => {
    const { container } = render(<GanttTimeline {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GanttTimeline.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<GanttTimeline {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<GanttTimeline {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<GanttTimeline {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _gantttask: GanttTask | undefined = undefined; void _gantttask;
    const _ganttviewmode: GanttViewMode | undefined = undefined; void _ganttviewmode;
    const _gantttimelineprops: GanttTimelineProps | undefined = undefined; void _gantttimelineprops;
    expect(true).toBe(true);
  });

  it('adds role="button" and keyboard support when onTaskClick provided', () => {
    const handler = vi.fn();
    const tasks = [{
      id: 't1',
      title: 'Task A',
      startDate: new Date('2026-01-01'),
      endDate: new Date('2026-01-10'),
      progress: 50,
    }];
    const { container } = render(<GanttTimeline tasks={tasks} onTaskClick={handler} />);
    const buttons = container.querySelectorAll('[role="button"]');
    expect(buttons.length).toBeGreaterThan(0);
    fireEvent.keyDown(buttons[0], { key: 'Enter' });
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
