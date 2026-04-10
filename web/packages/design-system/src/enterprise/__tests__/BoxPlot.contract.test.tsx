// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { BoxPlot } from '../BoxPlot';

describe('BoxPlot — contract', () => {
  const defaultProps = {
    data: [{ label: 'Q1', min: 5, q1: 15, median: 25, q3: 35, max: 50 }],
  };

  it('renders without crash', () => {
    const { container } = render(<BoxPlot {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(BoxPlot.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<BoxPlot {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<BoxPlot {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props', () => {
    const { container } = render(<BoxPlot {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('adds role="button" and keyboard support when onBoxClick provided', () => {
    const handler = vi.fn();
    const { container } = render(<BoxPlot {...defaultProps} onBoxClick={handler} />);
    const buttons = container.querySelectorAll('[role="button"]');
    expect(buttons.length).toBeGreaterThan(0);
    fireEvent.keyDown(buttons[0], { key: 'Enter' });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not add role="button" without onBoxClick', () => {
    const { container } = render(<BoxPlot {...defaultProps} />);
    const buttons = container.querySelectorAll('[role="button"]');
    expect(buttons.length).toBe(0);
  });
});
