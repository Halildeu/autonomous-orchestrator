// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { GalleryCard } from '../GalleryCard';
import type { GalleryItem } from '../types';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function createItem(overrides: Partial<GalleryItem> = {}): GalleryItem {
  return {
    id: '1',
    title: 'Test Report',
    group: 'HR',
    ...overrides,
  };
}

describe('GalleryCard — contract', () => {
  it('renders title', () => {
    render(<GalleryCard item={createItem()} />);
    expect(screen.getByText('Test Report')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(
      <GalleryCard item={createItem({ description: 'A detailed report' })} />,
    );
    expect(screen.getByText('A detailed report')).toBeInTheDocument();
  });

  it('renders icon as string emoji', () => {
    const { container } = render(
      <GalleryCard item={createItem({ icon: '📊' })} />,
    );
    expect(container.textContent).toContain('📊');
  });

  it('renders icon as ReactNode', () => {
    render(
      <GalleryCard item={createItem({ icon: <svg data-testid="custom-icon" /> })} />,
    );
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
  });

  it('calls onClick when card is clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(<GalleryCard item={createItem()} onClick={onClick} />);

    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('renders badge with label and tone', () => {
    render(
      <GalleryCard
        item={createItem({
          badge: { label: 'New', tone: 'success' },
        })}
      />,
    );
    expect(screen.getByText('New')).toBeInTheDocument();
  });

  it('renders badge with default tone when no tone specified', () => {
    const { container } = render(
      <GalleryCard
        item={createItem({
          badge: { label: 'Beta' },
        })}
      />,
    );

    const badgeEl = screen.getByText('Beta');
    // Default tone maps to "bg-surface-muted text-text-secondary"
    expect(badgeEl.className).toContain('bg-surface-muted');
  });

  it('renders tags as separate elements', () => {
    render(
      <GalleryCard
        item={createItem({
          tags: ['finance', 'monthly', 'export'],
        })}
      />,
    );

    expect(screen.getByText('finance')).toBeInTheDocument();
    expect(screen.getByText('monthly')).toBeInTheDocument();
    expect(screen.getByText('export')).toBeInTheDocument();
  });

  it('renders without optional fields (no crash on minimal item)', () => {
    const { container } = render(
      <GalleryCard item={{ id: 'min', title: 'Minimal', group: 'G' }} />,
    );
    expect(container.firstElementChild).toBeTruthy();
    expect(screen.getByText('Minimal')).toBeInTheDocument();
  });

  it('uses button element for keyboard accessibility', () => {
    render(<GalleryCard item={createItem()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('type', 'button');
  });
});
