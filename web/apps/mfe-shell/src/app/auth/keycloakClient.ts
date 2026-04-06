import Keycloak from 'keycloak-js';
import { authConfig } from './auth-config';

// STORY-0034: FE Keycloak / OIDC Integration
const keycloak = new Keycloak({
  url: authConfig.keycloak.url,
  realm: authConfig.keycloak.realm,
  clientId: authConfig.keycloak.clientId,
});

type KeycloakLoginRedirectOptions = {
  redirectUri: string;
};

const LOGIN_URL_TIMEOUT_MS = 3_000;

const summarizeUrl = (value: string): string => {
  try {
    const parsed = new URL(value);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return value;
  }
};

const navigateToLoginUrl = (loginUrl: string): void => {
  const currentHref = window.location.href;

  console.info(
    `[Auth] Redirecting to Keycloak login. current=${summarizeUrl(currentHref)} target=${summarizeUrl(loginUrl)}`,
  );

  window.location.assign(loginUrl);

  window.setTimeout(() => {
    if (window.location.href === currentHref) {
      console.warn(
        `[Auth] location.assign() did not change href. Retrying with replace. current=${summarizeUrl(currentHref)} target=${summarizeUrl(loginUrl)}`,
      );
      window.location.replace(loginUrl);
    }
  }, 250);
};

const readBrowserAuthRuntime = () => {
  if (typeof window === 'undefined') {
    return {
      currentHref: '',
      isSecureContext: false,
      hasCryptoSubtle: false,
    };
  }

  return {
    currentHref: window.location.href,
    isSecureContext: window.isSecureContext,
    hasCryptoSubtle: Boolean(window.crypto?.subtle),
  };
};

export const startKeycloakLogin = async ({
  redirectUri,
}: KeycloakLoginRedirectOptions): Promise<void> => {
  const loginUrl = await resolveKeycloakLoginUrl({ redirectUri });
  if (loginUrl) {
    navigateToLoginUrl(loginUrl);
    return;
  }

  console.info(`[Auth] Falling back to keycloak.login(). redirectUri=${summarizeUrl(redirectUri)}`);
  await keycloak.login({ redirectUri });
};

export const resolveKeycloakLoginUrl = async ({
  redirectUri,
}: KeycloakLoginRedirectOptions): Promise<string | null> => {
  if (typeof window !== 'undefined') {
    const runtime = readBrowserAuthRuntime();
    const currentHref = runtime.currentHref;

    if (!runtime.isSecureContext) {
      console.warn(
        `[Auth] Insecure browser context detected. app=${summarizeUrl(currentHref)} keycloak=${summarizeUrl(authConfig.keycloak.url)} secureContext=${runtime.isSecureContext} subtle=${runtime.hasCryptoSubtle}`,
      );
    }

    try {
      const loginUrl = await Promise.race<string>([
        keycloak.createLoginUrl({ redirectUri }),
        new Promise<string>((_, reject) => {
          window.setTimeout(() => {
            reject(
              new Error(
                `keycloak.createLoginUrl() timed out after ${LOGIN_URL_TIMEOUT_MS}ms`,
              ),
            );
          }, LOGIN_URL_TIMEOUT_MS);
        }),
      ]);
      if (loginUrl) {
        console.info(
          `[Auth] keycloak.createLoginUrl() resolved. current=${summarizeUrl(currentHref)} target=${summarizeUrl(loginUrl)} redirectUri=${summarizeUrl(redirectUri)} secureContext=${runtime.isSecureContext} subtle=${runtime.hasCryptoSubtle}`,
        );

        if (loginUrl !== currentHref) {
          return loginUrl;
        }

        console.warn(
          `[Auth] keycloak.createLoginUrl() returned current href. current=${summarizeUrl(currentHref)} redirectUri=${summarizeUrl(redirectUri)}`,
        );
      } else {
        console.warn(
          `[Auth] keycloak.createLoginUrl() returned an empty URL. redirectUri=${summarizeUrl(redirectUri)}`,
        );
      }

      if (loginUrl && loginUrl !== currentHref) {
        return loginUrl;
      }
    } catch (error) {
      console.error('[Auth] keycloak.createLoginUrl() failed:', error);
    }
  }

  return null;
};

export default keycloak;
