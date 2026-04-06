// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { FilterCombinatorRow } from '../data-grid/filter-builder/FilterCombinatorRow';
import type { FilterCombinator } from '../data-grid/filter-builder/types';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function createCombinator(logic: 'AND' | 'OR' = 'AND'): FilterCombinator {
  return {
    type: 'combinator',
    id: 'comb-1',
    logic,
  };
}

describe('FilterCombinatorRow — contract', () => {
  it('displays VE for AND combinator', () => {
    render(
      <FilterCombinatorRow
        combinator={createCombinator('AND')}
        onSetLogic={vi.fn()}
      />,
    );

    expect(screen.getByText('VE')).toBeInTheDocument();
  });

  it('displays VEYA for OR combinator', () => {
    render(
      <FilterCombinatorRow
        combinator={createCombinator('OR')}
        onSetLogic={vi.fn()}
      />,
    );

    expect(screen.getByText('VEYA')).toBeInTheDocument();
  });

  it('toggles AND to OR when clicked', async () => {
    const user = userEvent.setup();
    const onSetLogic = vi.fn();

    render(
      <FilterCombinatorRow
        combinator={createCombinator('AND')}
        onSetLogic={onSetLogic}
      />,
    );

    await user.click(screen.getByText('VE'));
    expect(onSetLogic).toHaveBeenCalledWith('comb-1', 'OR');
  });

  it('toggles OR to AND when clicked', async () => {
    const user = userEvent.setup();
    const onSetLogic = vi.fn();

    render(
      <FilterCombinatorRow
        combinator={createCombinator('OR')}
        onSetLogic={onSetLogic}
      />,
    );

    await user.click(screen.getByText('VEYA'));
    expect(onSetLogic).toHaveBeenCalledWith('comb-1', 'AND');
  });

  it('does NOT call onSetLogic when disabled', async () => {
    const user = userEvent.setup();
    const onSetLogic = vi.fn();

    render(
      <FilterCombinatorRow
        combinator={createCombinator('AND')}
        onSetLogic={onSetLogic}
        disabled={true}
      />,
    );

    const btn = screen.getByText('VE');
    expect(btn.closest('button')).toBeDisabled();
    await user.click(btn);
    expect(onSetLogic).not.toHaveBeenCalled();
  });

  it('renders branch lines on both sides', () => {
    const { container } = render(
      <FilterCombinatorRow
        combinator={createCombinator('AND')}
        onSetLogic={vi.fn()}
      />,
    );

    // Two decorative horizontal lines (border-subtle divs)
    const lines = container.querySelectorAll('.h-px');
    expect(lines.length).toBe(2);
  });
});
