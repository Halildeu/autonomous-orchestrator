import React from "react";
import { Provider } from "react-redux";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ToastProvider } from "@mfe/design-system";
import { PermissionProvider } from "@mfe/auth";
import type { AuthzMeResponse } from "@mfe/auth";
import { store } from "../store/store";
import { ThemeProvider } from "../theme/theme-context.provider";
import { I18nProvider, i18n } from "../i18n";
import { queryClient, shouldShowQueryDevtools } from "../config/query-config";
import { AuthBootstrapper } from "./AuthBootstrapper";
import { DownloadProgressListener } from "./DownloadProgressListener";
import { api } from "@mfe/shared-http";
import { isPermitAllMode } from "../auth/auth-config";
import { useAppSelector } from "../store/store.hooks";

// Side-effect imports — order matters
import "../config/http-config";
import "../config/shell-services-wiring";
import "../config/i18n-config";

const PermissionProviderWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, initialized, authzSnapshot } = useAppSelector((state) => state.auth);
  const permitAllMode = isPermitAllMode();
  const permissionFetchEnabled = permitAllMode || (initialized && Boolean(token));

  return (
    <PermissionProvider
      httpGet={api.get}
      permitAll={permitAllMode}
      enabled={permissionFetchEnabled}
      initialData={authzSnapshot as AuthzMeResponse | null}
    >
      {children}
    </PermissionProvider>
  );
};

/* ------------------------------------------------------------------ */
/*  AppProviders — Composes all shell-level providers                  */
/* ------------------------------------------------------------------ */

declare global {
  interface Window {
    __shellStore?: typeof store;
  }
}

export const AppProviders: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
    window.__shellStore = store;
  }

  return (
    <Provider store={store}>
      <ThemeProvider>
        <I18nProvider manager={i18n}>
          <QueryClientProvider client={queryClient}>
            <ToastProvider
              position="top-right"
              duration={4500}
              maxVisible={4}
            >
              <DownloadProgressListener />
              <AuthBootstrapper>
                <PermissionProviderWrapper>
                  {children}
                </PermissionProviderWrapper>
              </AuthBootstrapper>
            </ToastProvider>
            {shouldShowQueryDevtools ? (
              <ReactQueryDevtools initialIsOpen={false} />
            ) : null}
          </QueryClientProvider>
        </I18nProvider>
      </ThemeProvider>
    </Provider>
  );
};
