import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAppSelector } from '../store/store.hooks';
import { usePermissions } from '@mfe/auth';
import { useAuthorization } from '../../features/auth/model/use-authorization.model';
import { isPermitAllMode } from '../auth/auth-config';

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** @deprecated Use requiredModule instead for OpenFGA-based checks. */
  requiredPermissions?: string[];
  /** OpenFGA module key — preferred over requiredPermissions. */
  requiredModule?: string;
  fallbackPath?: string;
}

export const ProtectedRoute = ({
  children,
  requiredPermissions,
  requiredModule,
  fallbackPath = '/unauthorized',
}: ProtectedRouteProps) => {
  const { token, initialized } = useAppSelector((state) => state.auth);
  const { hasModule, isSuperAdmin } = usePermissions();
  const { hasPermission } = useAuthorization();
  const location = useLocation();
  const permitAllMode = isPermitAllMode();

  if (!initialized) {
    return null;
  }

  if (permitAllMode) {
    return <>{children}</>;
  }

  const buildRedirectTarget = () => {
    const composed = `${location.pathname ?? ''}${location.search ?? ''}${location.hash ?? ''}`;
    return encodeURIComponent(composed || '/');
  };

  if (!token) {
    const redirect = buildRedirectTarget();
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  // Module-based check (preferred)
  let canAccess: boolean;
  if (requiredModule) {
    canAccess = isSuperAdmin() || hasModule(requiredModule);
  } else if (requiredPermissions) {
    // Legacy string-based check (backward compat)
    canAccess = hasPermission(requiredPermissions);
  } else {
    canAccess = true;
  }

  if (!canAccess) {
    return (
      <Navigate
        to={fallbackPath}
        replace
        state={{
          from: location.pathname,
          reason: requiredModule ? 'module_denied' : 'forbidden',
          requiredModule,
        }}
      />
    );
  }

  return <>{children}</>;
};
