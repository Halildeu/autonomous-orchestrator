// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';

// Mock useSidebar — ShellSidebarInner depends on SidebarProvider context
const mockToggle = vi.fn();
const mockExpand = vi.fn();
const mockCollapse = vi.fn();
let mockIsCollapsed = false;

vi.mock('../../components/app-sidebar/useSidebar', () => ({
  SidebarContext: React.createContext(null),
  useSidebar: () => ({
    mode: mockIsCollapsed ? 'collapsed' : 'expanded',
    toggle: mockToggle,
    expand: mockExpand,
    collapse: mockCollapse,
    isCollapsed: mockIsCollapsed,
    resize: null,
    setWidth: vi.fn(),
    setIsResizing: vi.fn(),
  }),
}));

// Mock AppSidebar to pass through children without needing SidebarProvider
vi.mock('../../components/app-sidebar', () => {
  const Passthrough: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children }) => (
    <div data-testid="app-sidebar">{children}</div>
  );
  Passthrough.displayName = 'AppSidebar';

  const Trigger: React.FC = () => <button data-testid="sidebar-trigger">Toggle</button>;
  const Nav: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children }) => (
    <nav data-testid="sidebar-nav">{children}</nav>
  );
  const NavItem: React.FC<{ label: string; icon?: React.ReactNode; active?: boolean; disabled?: boolean; badge?: React.ReactNode; onClick?: () => void; className?: string }> = ({ label, onClick, active }) => (
    <button data-testid={`nav-${label}`} onClick={onClick} aria-current={active ? 'page' : undefined}>{label}</button>
  );
  const Footer: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
    <div data-testid="sidebar-footer">{children}</div>
  );
  const FooterAction: React.FC<{ label: string; icon?: React.ReactNode; onClick?: () => void; href?: string; disabled?: boolean; badge?: React.ReactNode; active?: boolean }> = ({ label, onClick }) => (
    <button data-testid={`footer-action-${label}`} onClick={onClick}>{label}</button>
  );
  const FooterStatus: React.FC<{ status?: string; label?: string; pulse?: boolean }> = ({ status, label }) => (
    <div data-testid="footer-status" data-status={status}>{label ?? status}</div>
  );

  const AppSidebar = Object.assign(Passthrough, { Trigger, Nav, NavItem, Footer, FooterAction, FooterStatus });
  return { AppSidebar, useSidebar: () => ({
    mode: mockIsCollapsed ? 'collapsed' : 'expanded',
    toggle: mockToggle,
    expand: mockExpand,
    collapse: mockCollapse,
    isCollapsed: mockIsCollapsed,
    resize: null,
    setWidth: vi.fn(),
    setIsResizing: vi.fn(),
  }) };
});

// Mock primitives that ShellSidebar uses
vi.mock('../../primitives/command-palette-trigger', () => ({
  CommandPaletteTrigger: ({ onClick, placeholder }: { onClick?: () => void; placeholder?: string; shortcut?: string; compact?: boolean }) => (
    <button data-testid="search-trigger" onClick={onClick}>{placeholder}</button>
  ),
}));

vi.mock('../../primitives/fullscreen-toggle', () => ({
  FullscreenToggle: ({ showLabel }: { showLabel?: boolean; variant?: string; className?: string }) => (
    <button data-testid="fullscreen-toggle">{showLabel ? 'Fullscreen' : 'FS'}</button>
  ),
}));

import { ShellSidebar } from '../shell-sidebar/ShellSidebar';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockIsCollapsed = false;
});

describe('ShellSidebar — contract', () => {
  const baseNavItems = [
    { key: 'home', label: 'Home', icon: <span>H</span> },
    { key: 'settings', label: 'Settings', icon: <span>S</span> },
  ];

  it('renders nav items and brand title in expanded mode', () => {
    render(
      <ShellSidebar
        navItems={baseNavItems}
        brandTitle="TestApp"
        brandSubtitle="v1.0"
      />,
    );

    expect(screen.getByText('TestApp')).toBeInTheDocument();
    expect(screen.getByText('v1.0')).toBeInTheDocument();
    expect(screen.getByTestId('nav-Home')).toBeInTheDocument();
    expect(screen.getByTestId('nav-Settings')).toBeInTheDocument();
  });

  it('calls onNavigate with key and item when nav item clicked', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    render(
      <ShellSidebar
        navItems={baseNavItems}
        onNavigate={onNavigate}
      />,
    );

    await user.click(screen.getByTestId('nav-Home'));
    expect(onNavigate).toHaveBeenCalledWith('home', baseNavItems[0]);
  });

  it('renders folder toggle and expands folder list on click', async () => {
    const user = userEvent.setup();
    const folderItems = [
      { key: 'inbox', label: 'Inbox', count: 5 },
      { key: 'sent', label: 'Sent', count: 12 },
    ];

    render(
      <ShellSidebar
        navItems={baseNavItems}
        folderItems={folderItems}
        foldersLabel="My Folders"
      />,
    );

    const folderToggle = screen.getByTitle('My Folders');
    expect(folderToggle).toBeInTheDocument();

    // Initially folder list is not visible
    expect(screen.queryByText('Inbox')).not.toBeInTheDocument();

    // Click to expand
    await user.click(folderToggle);
    expect(screen.getByText('Inbox')).toBeInTheDocument();
    expect(screen.getByText('Sent')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();

    // Click again to collapse
    await user.click(folderToggle);
    expect(screen.queryByText('Inbox')).not.toBeInTheDocument();
  });

  it('calls expand() and opens folders when folder toggle clicked in collapsed mode', async () => {
    mockIsCollapsed = true;
    const user = userEvent.setup();
    const folderItems = [{ key: 'inbox', label: 'Inbox', count: 3 }];

    render(
      <ShellSidebar
        navItems={baseNavItems}
        folderItems={folderItems}
        foldersLabel="Folders"
      />,
    );

    await user.click(screen.getByTitle('Folders'));
    expect(mockExpand).toHaveBeenCalled();
  });

  it('syncs CSS width variable on document root', () => {
    render(
      <ShellSidebar
        navItems={baseNavItems}
        cssWidthVar="--shell-sidebar-w"
        expandedWidth={280}
        collapsedWidth={60}
      />,
    );

    const rootStyle = document.documentElement.style.getPropertyValue('--shell-sidebar-w');
    expect(rootStyle).toBe('280px');
  });

  it('renders footer with status indicator', () => {
    render(
      <ShellSidebar
        navItems={baseNavItems}
        statusIndicator={{ status: 'online', label: 'Connected' }}
      />,
    );

    expect(screen.getByTestId('footer-status')).toBeInTheDocument();
  });

  it('renders custom footer content via renderFooter', () => {
    render(
      <ShellSidebar
        navItems={baseNavItems}
        renderFooter={({ isCollapsed }) => (
          <div data-testid="custom-footer">{isCollapsed ? 'C' : 'Expanded'}</div>
        )}
      />,
    );

    expect(screen.getByTestId('custom-footer')).toHaveTextContent('Expanded');
  });

  it('renders footer actions', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <ShellSidebar
        navItems={baseNavItems}
        footerActions={[
          { key: 'help', label: 'Help', icon: <span>?</span>, onClick },
        ]}
      />,
    );

    const helpBtn = screen.getByTestId('footer-action-Help');
    await user.click(helpBtn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('hides brand title and subtitle when collapsed', () => {
    mockIsCollapsed = true;

    render(
      <ShellSidebar
        navItems={baseNavItems}
        brandTitle="TestApp"
        brandSubtitle="v1.0"
      />,
    );

    expect(screen.queryByText('TestApp')).not.toBeInTheDocument();
    expect(screen.queryByText('v1.0')).not.toBeInTheDocument();
  });
});
