import React, { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../store/store.hooks";
import keycloak from "../auth/keycloakClient";
import { authConfig, isKeycloakMode } from "../auth/auth-config";
import {
  logout,
  setKeycloakSession,
  setAuthInitialized,
} from "../../features/auth/model/auth.slice";
import {
  subscribeAuthState,
  withSuppressedAuthBroadcast,
} from "../auth/auth-sync";
import { createDevAuthSession, mapKeycloakProfile } from "../config/auth-helpers";
import { api } from "@mfe/shared-http";
import { registerGridVariantsTokenResolver } from "@mfe/design-system";

/* ------------------------------------------------------------------ */
/*  Fetch real application permissions from permission-service          */
/* ------------------------------------------------------------------ */

interface AuthzMeResult {
  permissions: string[];
  superAdmin: boolean;
  /** Full /v1/authz/me response for PermissionProvider (avoids double fetch). */
  rawResponse: Record<string, unknown> | null;
}

async function fetchAppPermissions(token: string): Promise<AuthzMeResult> {
  try {
    const res = await api.get("/v1/authz/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = res.data as Record<string, unknown> & {
      permissions?: string[];
      allowedModules?: string[];
      superAdmin?: boolean;
    };
    const superAdmin = data?.superAdmin === true;
    // Prefer allowedModules (OpenFGA) over legacy permissions
    if (Array.isArray(data?.allowedModules) && data.allowedModules.length > 0) {
      return { permissions: data.allowedModules, superAdmin, rawResponse: data };
    }
    return {
      permissions: Array.isArray(data?.permissions) ? data.permissions : [],
      superAdmin,
      rawResponse: data,
    };
  } catch (err: unknown) {
    console.warn("AuthBootstrapper: /v1/authz/me failed, falling back to JWT roles", err);
    return { permissions: [], superAdmin: false, rawResponse: null };
  }
}

/**
 * Store token in httpOnly cookie via gateway endpoint.
 * Falls back silently if endpoint unavailable (dev mode).
 */
async function setTokenCookie(token: string): Promise<void> {
  try {
    await api.post("/auth/cookie", null, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    // Cookie endpoint may not be available in dev; silently ignore
  }
}

async function clearTokenCookie(): Promise<void> {
  try {
    await api.delete("/auth/cookie");
  } catch {
    // Silently ignore
  }
}

/* ------------------------------------------------------------------ */
/*  AuthBootstrapper — Keycloak initialization & token management      */
/* ------------------------------------------------------------------ */

export const AuthBootstrapper: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const dispatch = useAppDispatch();
  const token = useAppSelector((state) => state.auth.token);
  const tokenRef = useRef<string | null>(null);
  const shouldUseKeycloak = isKeycloakMode();

  useEffect(() => {
    tokenRef.current = token ?? null;
    // Register token resolver for grid variant API calls
    registerGridVariantsTokenResolver(() => tokenRef.current);
  }, [token]);

  /* Cross-window auth state subscription */
  useEffect(() => {
    if (!shouldUseKeycloak) {
      dispatch(setAuthInitialized(true));
      return () => undefined;
    }
    const unsubscribe = subscribeAuthState((payload) => {
      withSuppressedAuthBroadcast(() => {
        if (!payload?.token) {
          dispatch(logout());
          dispatch(setAuthInitialized(true));
          return;
        }
        dispatch(
          setKeycloakSession({
            token: payload.token,
            profile: payload.profile ?? undefined,
            expiresAt: payload.expiresAt ?? null,
          }),
        );
        dispatch(setAuthInitialized(true));
      });
    });
    return unsubscribe;
  }, [dispatch, shouldUseKeycloak]);

  /* Keycloak bootstrap */
  useEffect(() => {
    if (!shouldUseKeycloak) {
      if (authConfig.enableFakeAuth) {
        // Try real Keycloak token first (async), fallback to fake JWT
        createDevAuthSession().then((session) => {
          dispatch(
            setKeycloakSession({
              token: session.token,
              profile: session.profile ?? undefined,
              expiresAt: session.expiresAt,
            }),
          );
          dispatch(setAuthInitialized(true));
        });
        return;
      } else {
        dispatch(setKeycloakSession({ token: null }));
      }
      dispatch(setAuthInitialized(true));
      return;
    }
    let mounted = true;

    const bootstrap = async () => {
      try {
        const isLoginRoute =
          typeof window !== "undefined" &&
          window.location?.pathname?.startsWith("/login");
        // Detect auth code in URL (from Keycloak redirect after login)
        const urlHasAuthCode =
          typeof window !== "undefined" &&
          (window.location?.hash?.includes("code=") ||
           window.location?.search?.includes("code="));
        const initOptions: {
          pkceMethod: "S256";
          checkLoginIframe: false;
          onLoad?: "check-sso";
          silentCheckSsoRedirectUri?: string;
        } = {
          pkceMethod: "S256",
          checkLoginIframe: false,
        };
        // If URL has auth code, always use check-sso so keycloak.init()
        // processes the code and exchanges it for a token via PKCE.
        // Without onLoad, keycloak-js ignores the code in the URL.
        if (urlHasAuthCode) {
          initOptions.onLoad = "check-sso";
        } else if (!isLoginRoute && authConfig.keycloak.enableSilentCheckSso) {
          initOptions.onLoad = "check-sso";
          initOptions.silentCheckSsoRedirectUri =
            authConfig.keycloak.silentCheckSsoRedirectUri;
        }
        console.info('[AuthBootstrapper] init starting', {
          isLoginRoute, urlHasAuthCode, onLoad: initOptions.onLoad,
          kcUrl: authConfig.keycloak.url,
        });
        await keycloak.init(initOptions);
        console.info('[AuthBootstrapper] init done', {
          authenticated: keycloak.authenticated, hasToken: !!keycloak.token,
        });
        if (!mounted) return;
        const kcToken = keycloak.token ?? null;
        if (kcToken) {
          // Store token in httpOnly cookie for secure session management
          void setTokenCookie(kcToken);
          const profile = mapKeycloakProfile(kcToken);
          // Fetch real application permissions from authorization proxy
          const authzResult = await fetchAppPermissions(kcToken);
          const mergedProfile = profile
            ? {
                ...profile,
                permissions: authzResult.permissions.length > 0
                  ? authzResult.permissions
                  : profile.permissions,
                role: authzResult.superAdmin
                  ? "ADMIN"
                  : authzResult.permissions.length > 0
                    ? (authzResult.permissions.find((p) => p === "ADMIN") ?? profile.role)
                    : profile.role,
              }
            : undefined;
          dispatch(
            setKeycloakSession({
              token: kcToken,
              profile: mergedProfile,
              expiresAt: keycloak.tokenParsed?.exp
                ? keycloak.tokenParsed.exp * 1000
                : null,
              authzSnapshot: authzResult.rawResponse,
            }),
          );
        } else {
          if (!tokenRef.current) {
            dispatch(setKeycloakSession({ token: null }));
          }
        }
      } catch (err: unknown) {
        console.error('[AuthBootstrapper] keycloak.init() failed:', err);
        if (mounted && !tokenRef.current) {
          dispatch(setKeycloakSession({ token: null }));
        }
      } finally {
        if (mounted) {
          dispatch(setAuthInitialized(true));
        }
      }
    };

    bootstrap();

    keycloak.onTokenExpired = async () => {
      try {
        const refreshed = await keycloak.updateToken(60);
        if (refreshed && keycloak.token) {
          void setTokenCookie(keycloak.token);
          const profile = mapKeycloakProfile(keycloak.token);
          const authzResult = await fetchAppPermissions(keycloak.token);
          const mergedProfile = profile
            ? {
                ...profile,
                permissions: authzResult.permissions.length > 0
                  ? authzResult.permissions
                  : profile.permissions,
                role: authzResult.superAdmin
                  ? "ADMIN"
                  : authzResult.permissions.length > 0
                    ? (authzResult.permissions.find((p) => p === "ADMIN") ?? profile.role)
                    : profile.role,
              }
            : undefined;
          dispatch(
            setKeycloakSession({
              token: keycloak.token,
              profile: mergedProfile,
              expiresAt: keycloak.tokenParsed?.exp
                ? keycloak.tokenParsed.exp * 1000
                : null,
              authzSnapshot: authzResult.rawResponse,
            }),
          );
        }
      } catch (refreshError) {
        // Token refresh failed — log but don't logout.
        // Keycloak SSO session may still be valid for re-auth.
        console.warn('[AuthBootstrapper] Token refresh failed:', refreshError);
        void clearTokenCookie();
      }
    };

    return () => {
      mounted = false;
    };
  }, [dispatch, shouldUseKeycloak]);

  return <>{children}</>;
};
