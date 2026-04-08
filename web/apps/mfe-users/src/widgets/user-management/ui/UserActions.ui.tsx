import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { UserSummary } from '@mfe/shared-types';
import { useUserMutations } from '../../../features/user-management/model/use-users-query.model';
import { usePermissions } from '@mfe/auth';
import { useAuthorization } from '../../../features/user-management/model/use-authorization.model';
import { PERMISSIONS } from '../../../features/user-management/lib/permissions.constants';
import { useUsersI18n } from '../../../i18n/useUsersI18n';
import { pushToast } from '../../../shared/notifications';

interface UserActionsProps {
  user: UserSummary;
  onSelect: () => void;
}

const UserActions: React.FC<UserActionsProps> = ({ user, onSelect }) => {
  const { resetPasswordMutation, toggleStatusMutation } = useUserMutations();
  const { hasPermission } = useAuthorization();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const { t } = useUsersI18n();

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const items = useMemo(() => {
    const menu: { key: string; label: string; onClick: () => void }[] = [
      {
        key: 'view',
        label: t('users.actions.view'),
        onClick: onSelect,
      },
    ];

    if (hasPermission(PERMISSIONS.USER_MANAGEMENT_RESET_PASSWORD)) {
      menu.push({
        key: 'reset-password',
        label: t('users.actions.resetPassword'),
        onClick: async () => {
          try {
            await resetPasswordMutation.mutateAsync({ email: user.email });
            pushToast('success', t('users.actions.resetPassword.success'));
          } catch (error: unknown) {
            pushToast('error', (error as Error).message);
          }
        },
      });
    }

    if (hasPermission(PERMISSIONS.USER_MANAGEMENT_TOGGLE_STATUS)) {
      const nextEnabled = user.status !== 'ACTIVE';
      menu.push({
        key: 'toggle-status',
        label:
          user.status === 'ACTIVE'
            ? t('users.actions.toggleStatus.disable')
            : t('users.actions.toggleStatus.enable'),
        onClick: async () => {
          try {
            const result = await toggleStatusMutation.mutateAsync({ userId: user.id, enabled: nextEnabled });
            const auditId = result?.auditId;
            pushToast('success', t('users.actions.status.success'), auditId
              ? {
                description: t('users.notifications.activation.description', { auditId }),
                meta: {
                  auditId,
                  route: '/audit/events',
                  action: 'users.toggle_activation',
                  userId: user.id,
                  targetStatus: nextEnabled ? 'ACTIVE' : 'INACTIVE',
                },
                openInCenter: true,
              }
              : undefined);
          } catch (error: unknown) {
            pushToast('error', (error as Error).message);
          }
        },
      });
    }

    return menu;
  }, [hasPermission, onSelect, resetPasswordMutation, toggleStatusMutation, user.email, user.id, user.status]);

  return (
    <div className="relative inline-block" ref={containerRef}>
      <button
        type="button"
        className="rounded-md border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold text-text-secondary shadow-xs hover:bg-surface-muted"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((prev) => {
            const next = !prev;
            if (next && containerRef.current && typeof window !== 'undefined') {
              const rect = containerRef.current.getBoundingClientRect();
              setMenuPosition({
                top: rect.bottom + window.scrollY + 4,
                left: rect.right + window.scrollX - 192,
              });
            }
            return next;
          });
        }}
      >
        {t('users.actions.menuLabel')}
      </button>
      {open
        && menuPosition
        && typeof document !== 'undefined'
        && createPortal(
          <div
            className="fixed z-50 w-48 rounded-2xl border border-border-subtle bg-surface-default p-1 text-sm shadow-xl"
            style={{ top: menuPosition.top, left: menuPosition.left }}
          >
            {items.map((item) => (
              <button
                key={item.key}
                type="button"
                className="flex w-full items-center rounded-xl px-3 py-2 text-left text-text-secondary hover:bg-surface-muted"
                onClick={() => {
                  setOpen(false);
                  item.onClick();
                }}
              >
                {item.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
};

export default UserActions;
