// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';

// Mock useSidebar
let mockIsCollapsed = false;

vi.mock('../useSidebar', () => ({
  useSidebar: () => ({
    mode: mockIsCollapsed ? 'collapsed' : 'expanded',
    toggle: vi.fn(),
    expand: vi.fn(),
    collapse: vi.fn(),
    isCollapsed: mockIsCollapsed,
    resize: null,
    setWidth: vi.fn(),
    setIsResizing: vi.fn(),
  }),
}));

import { AppSidebarFooterAction } from '../AppSidebarFooterAction';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockIsCollapsed = false;
});

const TestIcon = () => <svg data-testid="test-icon" />;

describe('AppSidebarFooterAction — contract', () => {
  it('renders as button with onClick handler', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Settings"
        onClick={onClick}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Settings' });
    expect(btn).toBeInTheDocument();

    await user.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('renders as anchor tag when href is provided', () => {
    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Help"
        href="/help"
      />,
    );

    const link = screen.getByRole('link', { name: 'Help' });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/help');
  });

  it('blocks click when disabled', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Disabled Action"
        onClick={onClick}
        disabled={true}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Disabled Action' });
    expect(btn).toBeDisabled();

    // pointer-events-none via CSS class
    expect(btn.className).toContain('pointer-events-none');

    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders button (not anchor) when disabled even with href', () => {
    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Disabled Link"
        href="/disabled"
        disabled={true}
      />,
    );

    // Should render as button, not anchor, because disabled + href
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Disabled Link' })).toBeInTheDocument();
  });

  it('shows label text in expanded mode', () => {
    mockIsCollapsed = false;

    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Settings"
        onClick={vi.fn()}
      />,
    );

    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('hides label text in collapsed mode', () => {
    mockIsCollapsed = true;

    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Settings"
        onClick={vi.fn()}
      />,
    );

    // Label should NOT be in the DOM when collapsed (label span is conditionally rendered)
    const btn = screen.getByRole('button', { name: 'Settings' });
    // The visible text "Settings" is hidden (only aria-label remains)
    const labelSpan = btn.querySelector('span.truncate');
    expect(labelSpan).toBeNull();
  });

  it('renders badge when provided', () => {
    mockIsCollapsed = false;

    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Notifications"
        onClick={vi.fn()}
        badge={<span data-testid="badge">3</span>}
      />,
    );

    expect(screen.getByTestId('badge')).toBeInTheDocument();
  });

  it('hides badge in collapsed mode', () => {
    mockIsCollapsed = true;

    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Notifications"
        onClick={vi.fn()}
        badge={<span data-testid="badge">3</span>}
      />,
    );

    expect(screen.queryByTestId('badge')).not.toBeInTheDocument();
  });

  it('applies active styling when active prop is true', () => {
    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Active Item"
        onClick={vi.fn()}
        active={true}
      />,
    );

    const btn = screen.getByRole('button', { name: 'Active Item' });
    expect(btn.className).toContain('bg-surface-muted');
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef<HTMLDivElement>();

    render(
      <AppSidebarFooterAction
        ref={ref}
        icon={<TestIcon />}
        label="Ref Test"
        onClick={vi.fn()}
      />,
    );

    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });

  it('has correct displayName', () => {
    expect(AppSidebarFooterAction.displayName).toBe('AppSidebar.FooterAction');
  });

  it('passes data-testid to element', () => {
    render(
      <AppSidebarFooterAction
        icon={<TestIcon />}
        label="Test"
        onClick={vi.fn()}
        data-testid="my-action"
      />,
    );

    expect(screen.getByTestId('my-action')).toBeInTheDocument();
  });
});
