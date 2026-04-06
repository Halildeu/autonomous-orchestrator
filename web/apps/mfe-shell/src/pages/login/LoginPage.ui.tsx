import React, { useEffect, useMemo, useState } from 'react';
import { Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@mfe/design-system';
import { useShellCommonI18n } from '../../app/i18n';
import { resolveKeycloakLoginUrl, startKeycloakLogin } from '../../app/auth/keycloakClient';
import { buildAppRedirectUri, isPermitAllMode } from '../../app/auth/auth-config';
import { useAppSelector } from '../../app/store/store.hooks';

/**
 * LoginPage — Güvenli login sayfası
 *
 * OAuth 2.0 Authorization Code + PKCE akışı kullanır.
 * Kullanıcı Keycloak login sayfasına yönlendirilir (custom theme ile).
 * Şifre hiçbir zaman frontend'te işlenmez.
 *
 * Direct Grant (Resource Owner Password) kullanılMAZ:
 * - RFC 9700: "MUST NOT be used"
 * - OAuth 2.1'den kaldırılacak
 * - Keycloak 26'da deprecated
 */
const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useShellCommonI18n();
  const permitAllMode = isPermitAllMode();
  const { token, initialized } = useAppSelector((state) => state.auth);
  const [loginHref, setLoginHref] = useState<string | null>(null);
  const [loginHrefReady, setLoginHrefReady] = useState(false);
  const loginButtonClassName =
    'flex w-full items-center justify-center gap-2 rounded-lg bg-action-primary text-action-primary-text shadow-xs hover:opacity-90';

  const redirectPath = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const redirect = params.get('redirect');
    return redirect || '/';
  }, [location.search]);

  const redirectUri = useMemo(() => buildAppRedirectUri(redirectPath), [redirectPath]);

  useEffect(() => {
    let active = true;

    if (permitAllMode || !initialized) {
      setLoginHref(null);
      setLoginHrefReady(initialized);
      return () => {
        active = false;
      };
    }

    setLoginHrefReady(false);
    resolveKeycloakLoginUrl({ redirectUri })
      .then((value) => {
        if (!active) {
          return;
        }
        setLoginHref(value);
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        console.error('[LoginPage] resolveKeycloakLoginUrl() failed:', error);
        setLoginHref(null);
      })
      .finally(() => {
        if (active) {
          setLoginHrefReady(true);
        }
      });

    return () => {
      active = false;
    };
  }, [initialized, permitAllMode, redirectUri]);

  const handleLogin = () => {
    if (permitAllMode) {
      navigate(redirectPath);
      return;
    }
    if (!initialized) {
      return;
    }
    if (loginHref) {
      window.location.assign(loginHref);
      return;
    }
    startKeycloakLogin({ redirectUri }).catch((err) =>
      console.error('[LoginPage] startKeycloakLogin() failed:', err),
    );
  };

  if (initialized && token) {
    return <Navigate to={redirectPath} replace />;
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-6 py-10">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-border-subtle bg-surface-default p-8 shadow-xs">
          {/* Header */}
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-action-primary text-sm font-bold text-action-primary-text shadow-xs">
              S
            </div>
            <div>
              <h1 className="text-xl font-semibold text-text-primary">
                {t('auth.login.title') || 'Giriş Yap'}
              </h1>
              <p className="text-xs text-text-secondary">
                Kurumsal hesabınızla güvenli oturum açın
              </p>
            </div>
          </div>

          {permitAllMode ? (
            <div className="rounded-xl border border-state-success-border bg-state-success-bg/50 px-4 py-3">
              <p className="text-xs font-medium text-state-success-text">
                Geliştirme modunda oturum açmaya gerek yok.
              </p>
              <Button
                type="button"
                className="mt-3 w-full bg-action-primary text-action-primary-text hover:opacity-90"
                onClick={handleLogin}
              >
                Devam Et
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* Güvenli SSO Login */}
              {loginHref ? (
                <a
                  href={loginHref}
                  className={loginButtonClassName}
                  onClick={handleLogin}
                  data-testid="corporate-login-button"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  Güvenli Kurumsal Giriş
                </a>
              ) : (
                <Button
                  type="button"
                  className={loginButtonClassName}
                  onClick={handleLogin}
                  data-testid="corporate-login-button"
                  disabled={!initialized || !loginHrefReady}
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  Güvenli Kurumsal Giriş
                </Button>
              )}

              {!initialized || !loginHrefReady ? (
                <p className="text-[11px] text-text-secondary" data-testid="corporate-login-pending">
                  Kurumsal kimlik doğrulama hazırlanıyor...
                </p>
              ) : null}

              {/* Güvenlik bilgisi */}
              <div className="rounded-xl border border-border-subtle bg-surface-muted/50 px-4 py-3">
                <div className="flex items-start gap-2">
                  <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-state-success-text" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    <path d="m9 12 2 2 4-4" />
                  </svg>
                  <div>
                    <p className="text-[11px] font-medium text-text-primary">
                      Güvenli oturum açma
                    </p>
                    <p className="mt-0.5 text-[10px] text-text-tertiary">
                      OAuth 2.0 Authorization Code + PKCE ile korunan kurumsal kimlik doğrulama.
                      Şifreniz yalnızca güvenli kimlik sağlayıcıda işlenir.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
