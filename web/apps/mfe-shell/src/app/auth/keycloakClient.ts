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

export const startKeycloakLogin = async ({
  redirectUri,
}: KeycloakLoginRedirectOptions): Promise<void> => {
  if (typeof window !== 'undefined') {
    try {
      const loginUrl = await keycloak.createLoginUrl({ redirectUri });
      if (loginUrl) {
        window.location.assign(loginUrl);
        return;
      }
    } catch (error) {
      console.error('[Auth] keycloak.createLoginUrl() failed:', error);
    }
  }

  await keycloak.login({ redirectUri });
};

export default keycloak;
