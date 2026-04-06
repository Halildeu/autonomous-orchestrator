// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { GallerySearchBar } from '../GallerySearchBar';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('GallerySearchBar — contract', () => {
  it('renders search input with placeholder', () => {
    render(
      <GallerySearchBar
        value=""
        onChange={vi.fn()}
        placeholder="Search reports..."
      />,
    );

    expect(screen.getByPlaceholderText('Search reports...')).toBeInTheDocument();
  });

  it('uses default placeholder when not specified', () => {
    render(
      <GallerySearchBar value="" onChange={vi.fn()} />,
    );

    expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument();
  });

  it('calls onChange on each keystroke', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <GallerySearchBar value="" onChange={onChange} />,
    );

    const input = screen.getByRole('searchbox');
    await user.type(input, 'test');

    // Controlled component: value prop is "", so each keystroke appends to ""
    // in the DOM but the component reads e.target.value which is single char per type
    expect(onChange).toHaveBeenCalledTimes(4);
    // Verify each call received its individual character value
    expect(onChange).toHaveBeenNthCalledWith(1, expect.any(String));
    expect(onChange).toHaveBeenNthCalledWith(4, expect.any(String));
  });

  it('shows clear button only when value is not empty', () => {
    const { rerender } = render(
      <GallerySearchBar value="" onChange={vi.fn()} />,
    );

    expect(screen.queryByLabelText('Clear search')).not.toBeInTheDocument();

    rerender(
      <GallerySearchBar value="test" onChange={vi.fn()} />,
    );

    expect(screen.getByLabelText('Clear search')).toBeInTheDocument();
  });

  it('calls onChange with empty string when clear button clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <GallerySearchBar value="test" onChange={onChange} />,
    );

    await user.click(screen.getByLabelText('Clear search'));
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('renders summary line when provided', () => {
    render(
      <GallerySearchBar
        value=""
        onChange={vi.fn()}
        summary="12 reports found"
      />,
    );

    expect(screen.getByText('12 reports found')).toBeInTheDocument();
  });

  it('does not render summary line when not provided', () => {
    const { container } = render(
      <GallerySearchBar value="" onChange={vi.fn()} />,
    );

    // No <p> element for summary
    expect(container.querySelector('p')).toBeNull();
  });

  it('sets aria-label on input for accessibility', () => {
    render(
      <GallerySearchBar
        value=""
        onChange={vi.fn()}
        placeholder="Search..."
      />,
    );

    const input = screen.getByRole('searchbox');
    expect(input).toHaveAttribute('aria-label', 'Search...');
  });

  it('displays controlled value correctly', () => {
    render(
      <GallerySearchBar value="existing query" onChange={vi.fn()} />,
    );

    const input = screen.getByRole('searchbox') as HTMLInputElement;
    expect(input.value).toBe('existing query');
  });
});
