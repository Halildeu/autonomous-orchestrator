import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Alert, Button } from '@mfe/design-system';
import { usePermissions } from '@mfe/auth';
import { useShellCommonI18n } from '../../app/i18n';

const REASON_MESSAGES: Record<string, { title: string; description: string }> = {
  module_denied: {
    title: 'Modül erişimi yok',
    description: 'Bu modül rolünüzde tanımlı değil. Yöneticinizden ilgili rolün atanmasını isteyebilirsiniz.',
  },
  scope_denied: {
    title: 'Veri erişimi yok',
    description: 'Bu şirket/proje/depo verilerine erişiminiz bulunmuyor. Scope atanması gerekiyor.',
  },
  action_denied: {
    title: 'İşlem engellenmiş',
    description: 'Bu işlem rolünüzde DENY olarak işaretlenmiş. Engelleme yöneticiniz tarafından kaldırılabilir.',
  },
};

const UnauthorizedPage: React.FC = () => {
  const location = useLocation();
  const { t } = useShellCommonI18n();
  const { authz } = usePermissions();

  const state = location.state as {
    from?: string;
    reason?: string;
    requiredModule?: string;
    requiredPermission?: string;
  } | null;

  const fromPath = state?.from ?? '/';
  const reason = state?.reason;
  const requiredModule = state?.requiredModule;
  const userRoles = authz?.roles ?? [];

  const reasonInfo = reason ? REASON_MESSAGES[reason] : null;

  return (
    <div className="mt-16 flex justify-center px-4">
      <div className="w-full max-w-xl rounded-2xl border border-border-subtle bg-surface-default p-6 shadow-xs">
        <h1 className="mb-3 text-xl font-semibold text-text-primary">
          {t('auth.unauthorized.title')}
        </h1>
        <p className="mb-4 text-sm text-text-secondary">
          {t('auth.unauthorized.description')}
        </p>

        {/* Detailed explanation */}
        {reasonInfo && (
          <Alert variant="warning" title={reasonInfo.title} className="mb-4">
            {reasonInfo.description}
          </Alert>
        )}

        {requiredModule && (
          <div className="mb-4 rounded-xl border border-border-subtle bg-surface-muted p-4 text-sm">
            <div className="flex justify-between">
              <span className="text-text-subtle">Gerekli modül:</span>
              <span className="font-semibold text-text-primary">{requiredModule}</span>
            </div>
            {userRoles.length > 0 && (
              <div className="flex justify-between mt-2">
                <span className="text-text-subtle">Mevcut rolleriniz:</span>
                <span className="font-medium text-text-primary">{userRoles.join(', ')}</span>
              </div>
            )}
            {userRoles.length === 0 && (
              <div className="mt-2 text-xs text-state-danger-text">
                Henüz hiçbir rol atanmamış. Yöneticinize başvurun.
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button className="bg-action-primary text-action-primary-text hover:opacity-90">
            <Link to={fromPath}>{t('auth.unauthorized.back')}</Link>
          </Button>
          <Button className="bg-surface-muted text-text-secondary hover:bg-surface-default">
            <Link to="/">{t('auth.unauthorized.home')}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
};

export default UnauthorizedPage;
