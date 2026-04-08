import React, { useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, Shield, Settings, User, LogOut } from 'lucide-react';
import { Avatar, Dropdown, Badge } from '@mfe/design-system';
import type { DropdownEntry } from '@mfe/design-system';
import { useAppDispatch, useAppSelector } from '../../store/store.hooks';
import { usePermissions } from '@mfe/auth';
import { MODULE_KEYS } from '../../../features/auth/lib/permissions.constants';
import { logout } from '../../../features/auth/model/auth.slice';
import { buildAppRedirectUri } from '../../auth/auth-config';
import keycloak from '../../auth/keycloakClient';
import { useShellCommonI18n } from '../../i18n';

/* ------------------------------------------------------------------ */
/*  UserMenuDropdown — Avatar trigger + rich dropdown menu             */
/* ------------------------------------------------------------------ */

function getInitials(user: { fullName?: string; displayName?: string; name?: string; email?: string } | null): string {
  const name = user?.fullName?.trim() || user?.displayName?.trim() || user?.name?.trim();
  if (name) {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0])
      .join('')
      .toUpperCase();
  }
  return (user?.email?.[0] ?? 'U').toUpperCase();
}

function getDisplayName(user: { fullName?: string; displayName?: string; name?: string; email?: string } | null, fallback: string): string {
  if (user?.fullName?.trim()) return user.fullName;
  if (user?.displayName?.trim()) return user.displayName;
  if (user?.name?.trim()) return user.name;
  if (user?.email) return user.email.split('@')[0];
  return fallback;
}

export const UserMenuDropdown: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAppSelector((s) => s.auth);
  const { hasModule, isSuperAdmin } = usePermissions();
  const { t, locale } = useShellCommonI18n();

  const canAudit = isSuperAdmin() || hasModule(MODULE_KEYS.AUDIT);
  const canThemeAdmin = isSuperAdmin() || hasModule(MODULE_KEYS.THEME);

  const initials = useMemo(() => getInitials(user), [user]);
  const displayName = useMemo(() => getDisplayName(user, t('shell.header.defaultUser')), [user, t]);

  const formattedLastLogin = useMemo(() => {
    if (!user?.lastLoginAt) return t('shell.header.neverLoggedIn');
    try {
      const date = new Date(user.lastLoginAt);
      const localeMap: Record<string, string> = { tr: 'tr-TR', en: 'en-US', de: 'de-DE', es: 'es-ES' };
      return date.toLocaleString(localeMap[locale] ?? undefined);
    } catch {
      return user.lastLoginAt;
    }
  }, [user?.lastLoginAt, locale, t]);

  const handleLogout = useCallback(() => {
    dispatch(logout());
    if (typeof window !== 'undefined') {
      keycloak
        .logout({ redirectUri: buildAppRedirectUri('/login'), federated: true })
        .catch(() => { /* keycloak unavailable */ });
    }
  }, [dispatch]);

  const items = useMemo<DropdownEntry[]>(() => {
    const entries: DropdownEntry[] = [];

    // User info header
    entries.push({
      key: 'user-info',
      label: (
        <div className="flex items-center gap-3 py-1">
          <Avatar initials={initials} size="md" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-text-primary">{displayName}</div>
            {user?.email && (
              <div className="truncate text-xs text-text-subtle">{user.email}</div>
            )}
            {user?.role && (
              <div className="mt-0.5 text-[11px] text-text-subtle">{user.role}</div>
            )}
          </div>
        </div>
      ),
      disabled: true,
    });

    entries.push({ type: 'separator' });

    // Last login
    entries.push({
      key: 'last-login',
      label: (
        <span className="text-xs text-text-subtle">
          {t('shell.header.lastLogin').replace('{value}', formattedLastLogin)}
        </span>
      ),
      disabled: true,
    });

    entries.push({ type: 'separator' });

    // Audit shortcuts (conditional)
    if (canAudit) {
      entries.push({
        key: 'audit',
        label: t('shell.nav.audit'),
        icon: <Shield className="h-4 w-4" />,
        onClick: () => navigate('/audit/events'),
      });
    }

    // Settings
    if (canThemeAdmin) {
      entries.push({
        key: 'settings',
        label: t('shell.userMenu.settings'),
        icon: <Settings className="h-4 w-4" />,
        onClick: () => navigate('/admin/themes'),
      });
    }

    // Profile (coming soon)
    entries.push({
      key: 'profile',
      label: (
        <span className="flex items-center gap-2">
          {t('shell.header.profileSoon')}
          <Badge variant="muted" size="sm">Yakında</Badge>
        </span>
      ),
      icon: <User className="h-4 w-4" />,
      disabled: true,
    });

    entries.push({ type: 'separator' });

    // Logout
    entries.push({
      key: 'logout',
      label: t('shell.header.logout'),
      icon: <LogOut className="h-4 w-4" />,
      danger: true,
      onClick: handleLogout,
    });

    return entries;
  }, [initials, displayName, user, formattedLastLogin, canAudit, canThemeAdmin, t, navigate, handleLogout]);

  return (
    <Dropdown items={items} placement="bottom-end" minWidth={260}>
      <button
        type="button"
        className="group inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-text-primary transition-all duration-150 hover:bg-surface-muted hover:shadow-[0_0_0_2px_var(--accent-primary)]/10"
        aria-label={t('shell.userMenu.title')}
      >
        <Avatar initials={initials} size="xs" />
        <span className="hidden max-w-[120px] truncate text-[13px] font-medium lg:inline">
          {displayName}
        </span>
        <ChevronDown className="h-3 w-3 text-text-subtle" aria-hidden />
      </button>
    </Dropdown>
  );
};
