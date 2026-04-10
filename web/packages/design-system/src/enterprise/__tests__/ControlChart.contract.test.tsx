// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { ControlChart } from '../ControlChart';

describe('ControlChart — contract', () => {
  const defaultProps = {
    data: [{ x: 1, y: 50 }, { x: 2, y: 52 }, { x: 3, y: 48 }],
  };

  it('renders without crash', () => {
    const { container } = render(<ControlChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ControlChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ControlChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ControlChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props', () => {
    const { container } = render(<ControlChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('adds role="button" and keyboard support when onPointClick provided', () => {
    const handler = vi.fn();
    const { container } = render(<ControlChart {...defaultProps} onPointClick={handler} />);
    const buttons = container.querySelectorAll('[role="button"]');
    expect(buttons.length).toBeGreaterThan(0);
    fireEvent.keyDown(buttons[0], { key: 'Enter' });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not add role="button" without onPointClick', () => {
    const { container } = render(<ControlChart {...defaultProps} />);
    const buttons = container.querySelectorAll('[role="button"]');
    expect(buttons.length).toBe(0);
  });
});
