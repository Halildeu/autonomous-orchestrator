// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import React from 'react';

// Mock useSidebar — component reads isCollapsed from context
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

// Mock StatusIndicator to inspect props
vi.mock('../../../primitives/status-indicator', () => ({
  StatusIndicator: ({ status, label, showLabel, pulse }: { status?: string; label?: string; showLabel?: boolean; pulse?: boolean }) => (
    <span
      data-testid="status-indicator"
      data-status={status}
      data-label={label}
      data-show-label={String(showLabel)}
      data-pulse={String(pulse)}
    >
      {showLabel ? label : ''}
    </span>
  ),
}));

import { AppSidebarFooterStatus } from '../AppSidebarFooterStatus';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockIsCollapsed = false;
});

describe('AppSidebarFooterStatus — contract', () => {
  it('renders StatusIndicator with correct status', () => {
    render(<AppSidebarFooterStatus status="online" />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-status', 'online');
  });

  it('defaults to "online" status when not specified', () => {
    render(<AppSidebarFooterStatus />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-status', 'online');
  });

  it('resolves label from status when no custom label provided', () => {
    render(<AppSidebarFooterStatus status="busy" />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-label', 'Busy');
  });

  it('uses custom label when provided', () => {
    render(<AppSidebarFooterStatus status="online" label="Connected" />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-label', 'Connected');
  });

  it('shows label text in expanded mode', () => {
    mockIsCollapsed = false;

    render(<AppSidebarFooterStatus status="online" label="Connected" />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-show-label', 'true');
  });

  it('hides label text and shows tooltip in collapsed mode', () => {
    mockIsCollapsed = true;

    render(<AppSidebarFooterStatus status="online" label="Connected" />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-show-label', 'false');

    // Tooltip element should exist
    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Connected');
  });

  it('passes pulse prop to StatusIndicator', () => {
    render(<AppSidebarFooterStatus status="online" pulse={true} />);

    const indicator = screen.getByTestId('status-indicator');
    expect(indicator).toHaveAttribute('data-pulse', 'true');
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<AppSidebarFooterStatus ref={ref} status="online" />);

    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });

  it('has correct displayName', () => {
    expect(AppSidebarFooterStatus.displayName).toBe('AppSidebar.FooterStatus');
  });

  it('applies additional className', () => {
    const { container } = render(
      <AppSidebarFooterStatus status="online" className="custom-class" />,
    );

    expect(container.firstElementChild).toHaveClass('custom-class');
  });
});
