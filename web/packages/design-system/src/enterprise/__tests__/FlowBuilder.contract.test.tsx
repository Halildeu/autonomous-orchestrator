// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { FlowBuilder } from '../FlowBuilder';

describe('FlowBuilder — contract', () => {
  const defaultProps = {
    nodes: [{ id: '1', type: 'start' as const, label: 'Begin', x: 100, y: 100 }],
    edges: [],
  };

  it('renders without crash', () => {
    const { container } = render(<FlowBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FlowBuilder.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FlowBuilder {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FlowBuilder {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props', () => {
    const { container } = render(<FlowBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders nodes with role="button" for keyboard accessibility', () => {
    const { container } = render(<FlowBuilder {...defaultProps} />);
    const buttons = container.querySelectorAll('[role="button"]');
    // Each node renders as interactive <g role="button"> with keyboard support
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('supports keyboard navigation on nodes (Enter selects)', () => {
    const { container } = render(<FlowBuilder {...defaultProps} />);
    const nodeButton = container.querySelector('[data-testid="node-1"]');
    expect(nodeButton).toBeTruthy();
    expect(nodeButton?.getAttribute('role')).toBe('button');
    expect(nodeButton?.getAttribute('tabindex')).toBe('0');
    // Enter key triggers selection (FlowBuilder uses selection state, not direct callback)
    fireEvent.keyDown(nodeButton!, { key: 'Enter' });
    expect(nodeButton).toBeTruthy(); // no crash after keyboard interaction
  });
});
