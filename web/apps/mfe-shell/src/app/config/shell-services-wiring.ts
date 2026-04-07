/* ------------------------------------------------------------------ */
/*  Shell services wiring — connects Redux store, telemetry, etc.      */
/* ------------------------------------------------------------------ */

import { api } from "@mfe/shared-http";
import { store } from "../store/store";
import {
  configureShellServices,
  type ShellNotificationEntry,
  type ShellTelemetryEvent,
} from "../services/shell-services";
import {
  pushNotification,
  toggleOpen,
} from "../../features/notifications/model/notifications.slice";
import telemetryClient from "../telemetry/telemetry-client";
import {
  broadcastAuthState,
} from "../auth/auth-sync";
import { queryClient } from "./query-config";
import { readEnvBoolean } from "./env";

/* ---- Notification dispatcher ---- */

export const pushShellNotification = (entry: ShellNotificationEntry) => {
  store.dispatch(pushNotification(entry));
  if (entry.meta?.open === true) {
    store.dispatch(toggleOpen(true));
  }
};

/* ---- Telemetry dispatcher ---- */

export const emitShellTelemetry = (event: ShellTelemetryEvent) => {
  telemetryClient.emit(event);
};

/* ---- Configure shell services ---- */

configureShellServices({
  queryClient,
  getAuthToken: () => store.getState().auth.token,
  subscribeAuthToken: (listener) => {
    const readAuthState = () => store.getState().auth;
    let previousToken = readAuthState().token ?? null;
    let previousExpiresAt = readAuthState().expiresAt ?? null;
    let previousProfileHash = JSON.stringify(readAuthState().user ?? null);

    const notify = () => {
      const nextState = readAuthState();
      const token = nextState.token ?? null;
      const expiresAt = nextState.expiresAt ?? null;
      const profileHash = JSON.stringify(nextState.user ?? null);

      if (token !== previousToken) {
        listener(token);
      }

      if (
        token !== previousToken ||
        expiresAt !== previousExpiresAt ||
        profileHash !== previousProfileHash
      ) {
        broadcastAuthState({
          token,
          expiresAt,
          profile: nextState.user ?? undefined,
        });
        previousToken = token;
        previousExpiresAt = expiresAt;
        previousProfileHash = profileHash;
      }
    };

    const unsubscribe = store.subscribe(notify);
    listener(previousToken ?? null);
    broadcastAuthState({
      token: previousToken ?? null,
      expiresAt: previousExpiresAt ?? null,
      profile: readAuthState().user ?? undefined,
    });
    return unsubscribe;
  },
  notify: pushShellNotification,
  telemetry: emitShellTelemetry,
  isFeatureEnabled: () => false,
});

/* ---- Wire remote module shell-services ---- */

export const wireRemoteShellServices = () => {
  if (typeof window === "undefined") {
    return;
  }
  if (
    readEnvBoolean("VITE_SHELL_SKIP_REMOTE_SERVICES") ||
    readEnvBoolean("SHELL_SKIP_REMOTE_SERVICES")
  ) {
    if (process.env.NODE_ENV !== "production") {
      console.debug(
        "[shell] remote shell-services yuklemesi environment ile kapatildi",
      );
    }
    return;
  }
  const sharedServices = {
    notify: { push: pushShellNotification },
    telemetry: { emit: emitShellTelemetry },
    http: api,
    auth: {
      getToken: () => store.getState().auth.token ?? null,
      getUser: () => store.getState().auth.user ?? null,
    },
  };
  const remotes = [
    { name: "mfe_access", loader: () => import("mfe_access/shell-services") },
    { name: "mfe_audit", loader: () => import("mfe_audit/shell-services") },
    { name: "mfe_users", loader: () => import("mfe_users/shell-services") },
    {
      name: "mfe_reporting",
      loader: () => import("mfe_reporting/shell-services"),
    },
  ];
  remotes.forEach(({ name, loader }) => {
    loader()
      .then((module) => module.configureShellServices(sharedServices))
      .catch((error) => {
        if (process.env.NODE_ENV !== "production") {
          console.debug(
            `[shell] ${name} shell-services konfigurasyonu atlandı`,
            error,
          );
        }
      });
  });
};

let remoteShellServicesWired = false;

const shouldWireRemoteShellServices = () => {
  const authState = store.getState().auth;
  return Boolean(authState.token) || authState.status === "succeeded";
};

const wireRemoteShellServicesWhenReady = () => {
  if (remoteShellServicesWired || !shouldWireRemoteShellServices()) {
    return;
  }
  remoteShellServicesWired = true;
  wireRemoteShellServices();
};

// Avoid eager remote evaluation on public routes like /login. Some remotes
// still pull React vendor chunks during shell-services import, which can
// white-screen the page before auth completes.
wireRemoteShellServicesWhenReady();

store.subscribe(() => {
  wireRemoteShellServicesWhenReady();
});
