// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { GalleryGroup } from '../GalleryGroup';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('GalleryGroup — contract', () => {
  it('renders group name and count', () => {
    render(
      <GalleryGroup name="HR Reports" count={5} expanded={true} onToggle={vi.fn()}>
        <div>Content</div>
      </GalleryGroup>,
    );

    expect(screen.getByText('HR Reports')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('calls onToggle when header button is clicked', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();

    render(
      <GalleryGroup name="Finance" count={3} expanded={true} onToggle={onToggle}>
        <div>Content</div>
      </GalleryGroup>,
    );

    await user.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('sets aria-expanded=true when expanded', () => {
    render(
      <GalleryGroup name="Group" count={1} expanded={true} onToggle={vi.fn()}>
        <div>Content</div>
      </GalleryGroup>,
    );

    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
  });

  it('sets aria-expanded=false when collapsed', () => {
    render(
      <GalleryGroup name="Group" count={1} expanded={false} onToggle={vi.fn()}>
        <div>Content</div>
      </GalleryGroup>,
    );

    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false');
  });

  it('marks content as aria-hidden=true when collapsed', () => {
    const { container } = render(
      <GalleryGroup name="Group" count={1} expanded={false} onToggle={vi.fn()}>
        <div data-testid="child">Hidden Content</div>
      </GalleryGroup>,
    );

    const contentWrapper = container.querySelector('[aria-hidden]');
    expect(contentWrapper).toHaveAttribute('aria-hidden', 'true');
  });

  it('marks content as aria-hidden=false when expanded', () => {
    const { container } = render(
      <GalleryGroup name="Group" count={1} expanded={true} onToggle={vi.fn()}>
        <div data-testid="child">Visible Content</div>
      </GalleryGroup>,
    );

    const contentWrapper = container.querySelector('[aria-hidden]');
    expect(contentWrapper).toHaveAttribute('aria-hidden', 'false');
  });

  it('renders children inside content area', () => {
    render(
      <GalleryGroup name="Group" count={1} expanded={true} onToggle={vi.fn()}>
        <div data-testid="child-content">Card Grid Here</div>
      </GalleryGroup>,
    );

    expect(screen.getByTestId('child-content')).toBeInTheDocument();
  });

  it('collapses content via max-height animation (height 0 when collapsed)', () => {
    const { container } = render(
      <GalleryGroup name="Group" count={2} expanded={false} onToggle={vi.fn()}>
        <div>Cards</div>
      </GalleryGroup>,
    );

    const contentWrapper = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    // Initially collapsed: maxHeight should be "0px"
    expect(contentWrapper.style.maxHeight).toBe('0px');
  });

  it('has data-component and data-group attributes for testing', () => {
    const { container } = render(
      <GalleryGroup name="Finance" count={5} expanded={true} onToggle={vi.fn()}>
        <div>Content</div>
      </GalleryGroup>,
    );

    const root = container.querySelector('[data-component="gallery-group"]');
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute('data-group', 'Finance');
  });
});
