import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { usePermissions } from '@mfe/auth';
import { useAuthorization } from '../../features/auth/model/use-authorization.model';
import { PERMISSIONS } from '../../features/auth/lib/permissions.constants';
import { useShellCommonI18n } from '../i18n';
import { useThemeContext } from '../theme/theme-context.provider';
import { isEthicRemoteEnabled, isSuggestionsRemoteEnabled } from '../shell-navigation';

const baseLauncherItems = [
  {
    key: 'home',
    icon: <span aria-hidden>🏠</span>,
    titleKey: 'shell.nav.home',
    descriptionKey: 'shell.launcher.home.description',
    to: '/',
  },
  {
    key: 'suggestions',
    icon: <span aria-hidden>💡</span>,
    titleKey: 'shell.nav.suggestions',
    descriptionKey: 'shell.launcher.suggestions.description',
    to: '/suggestions',
  },
  {
    key: 'ethic',
    icon: <span aria-hidden>⚖️</span>,
    titleKey: 'shell.nav.ethic',
    descriptionKey: 'shell.launcher.ethic.description',
    to: '/ethic',
  },
  {
    key: 'access',
    icon: <span aria-hidden>🔐</span>,
    titleKey: 'shell.nav.access',
    descriptionKey: 'shell.launcher.access.description',
    to: '/access/roles',
    requiredPermission: PERMISSIONS.ACCESS_MODULE,
  },
  {
    key: 'users',
    icon: <span aria-hidden>👥</span>,
    titleKey: 'shell.nav.users',
    descriptionKey: 'shell.launcher.users.description',
    to: '/admin/users',
    requiredPermission: PERMISSIONS.USER_MANAGEMENT_MODULE,
  },
];

const AppLauncher: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { hasPermission } = useAuthorization();
  const { t, locale } = useShellCommonI18n();
  const { axes } = useThemeContext();
  const suggestionsEnabled = isSuggestionsRemoteEnabled();
  const ethicEnabled = isEthicRemoteEnabled();
  const overlayStyle = useMemo(
    () => ({
      backgroundColor:
        `color-mix(in srgb, var(--surface-overlay-bg) ${axes.overlayIntensity}%, transparent)`,
      opacity: axes.overlayOpacity / 100,
    }),
    [axes.overlayOpacity, axes.overlayIntensity],
  );

  const launcherItems = useMemo(() => (
    baseLauncherItems
      .filter((item) => {
        if (item.key === 'suggestions') {
          return suggestionsEnabled;
        }
        if (item.key === 'ethic') {
          return ethicEnabled;
        }
        return true;
      })
      .filter((item) => !item.requiredPermission || hasPermission(item.requiredPermission))
      .map((item) => ({
        ...item,
        title: t(item.titleKey),
        description: t(item.descriptionKey),
      }))
  ), [ethicEnabled, hasPermission, locale, suggestionsEnabled, t]);

  return (
    <div className="fixed inset-0 z-[1600]" role="dialog" aria-modal="true" aria-label={t('shell.launcher.title')}>
      <div
        className="absolute inset-0 bg-surface-overlay"
        style={overlayStyle}
        aria-hidden="true"
        onClick={onClose}
      />
      <div className="absolute left-6 top-16 w-[360px] rounded-2xl border border-border-subtle bg-surface-panel shadow-xl">
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2">
          <span className="text-sm font-semibold text-text-primary">
            🧩 {t('shell.launcher.title')}
          </span>
          <button
            type="button"
            className="text-xs font-medium text-text-subtle hover:text-text-secondary"
            onClick={onClose}
          >
            {t('shell.launcher.close')}
          </button>
        </div>
        <div className="flex flex-col gap-2 p-3">
          {launcherItems.map((item) => (
            <Link
              key={item.key}
              to={item.to}
              onClick={onClose}
              className="group block rounded-xl border border-border-subtle bg-surface-default px-3 py-2 text-sm shadow-xs hover:border-action-primary-border hover:bg-surface-muted"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-muted text-lg">
                  {item.icon}
                </span>
                <div>
                  <div className="font-semibold text-text-primary group-hover:text-action-primary-text">
                    {item.title}
                  </div>
                  <div className="text-xs text-text-subtle">{item.description}</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AppLauncher;
