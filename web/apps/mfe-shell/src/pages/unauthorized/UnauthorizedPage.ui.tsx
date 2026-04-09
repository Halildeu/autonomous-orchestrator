import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Alert, Badge, Button } from '@mfe/design-system';
import { usePermissions, useExplainPermission } from '@mfe/auth';
import type { ExplainResponse } from '@mfe/auth';
import { api } from '@mfe/shared-http';
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

const EXPLAIN_REASON_LABELS: Record<ExplainResponse['reason'], { label: string; variant: 'success' | 'error' | 'warning' }> = {
  ALLOWED: { label: 'Erişim izni verilmiş.', variant: 'success' },
  NO_ROLE: { label: 'Kullanıcıya hiç rol atanmamış.', variant: 'error' },
  DENIED_BY_ROLE: { label: 'Roldeki DENY kuralı erişimi engelliyor.', variant: 'error' },
  NO_SCOPE: { label: 'Kullanıcının bu kapsam (scope) için izni yok.', variant: 'warning' },
  NO_PERMISSION: { label: 'Bu izin hiçbir rolde tanımlanmamış.', variant: 'error' },
};

const UnauthorizedPage: React.FC = () => {
  const location = useLocation();
  const { t } = useShellCommonI18n();
  const { authz } = usePermissions();
  const { explain, result: explainResult, loading: explainLoading, error: explainError } = useExplainPermission({
    httpPost: (url, body) => api.post(url, body),
  });

  const state = location.state as {
    from?: string;
    reason?: string;
    requiredModule?: string;
    requiredPermission?: string;
  } | null;

  const fromPath = state?.from ?? '/';
  const reason = state?.reason;
  const requiredModule = state?.requiredModule;
  const requiredPermission = state?.requiredPermission;
  const userRoles = authz?.roles ?? [];
  const userId = (authz as Record<string, unknown>)?.userId as string | undefined;

  const reasonInfo = reason ? REASON_MESSAGES[reason] : null;

  const handleExplain = async () => {
    if (!userId) return;
    const permType = requiredPermission ? 'ACTION' : 'MODULE';
    const permKey = requiredPermission ?? requiredModule ?? '';
    if (!permKey) return;
    await explain(userId, permType, permKey);
  };

  const canExplain = !!userId && !!(requiredModule || requiredPermission);

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

        {/* Explain result from server */}
        {explainResult && (
          <div className="mb-4 rounded-xl border border-border-subtle bg-surface-muted p-4 text-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-text-primary">Sunucu açıklaması:</span>
              <Badge variant={EXPLAIN_REASON_LABELS[explainResult.reason]?.variant ?? 'error'} size="sm">
                {explainResult.reason}
              </Badge>
            </div>
            <p className="text-text-secondary mb-2">
              {EXPLAIN_REASON_LABELS[explainResult.reason]?.label ?? explainResult.reason}
            </p>
            {explainResult.details?.roleName && (
              <div className="flex justify-between">
                <span className="text-text-subtle">Kaynak rol:</span>
                <span className="font-medium text-text-primary">{explainResult.details.roleName}</span>
              </div>
            )}
            {explainResult.userRoles?.length > 0 && (
              <div className="flex justify-between mt-1">
                <span className="text-text-subtle">Roller:</span>
                <span className="font-medium text-text-primary">{explainResult.userRoles.join(', ')}</span>
              </div>
            )}
          </div>
        )}

        {explainError && (
          <Alert variant="error" title="Explain hatası" className="mb-4">
            {explainError}
          </Alert>
        )}

        <div className="flex flex-wrap gap-2">
          {canExplain && !explainResult && (
            <Button variant="secondary" onClick={handleExplain} loading={explainLoading}>
              Neden erişemiyorum?
            </Button>
          )}
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
