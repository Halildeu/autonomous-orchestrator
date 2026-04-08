import React, { useEffect, useCallback } from "react";
import { BrowserRouter, useLocation } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "../store/store.hooks";
import { useThemeContext } from "../theme/theme-context.provider";
import { useToast, useBreakpoint } from "@mfe/design-system";
import { useShellCommonI18n } from "../i18n";
import { useShellShortcuts } from "../shortcuts/useShellShortcuts.model";
import { fetchProducts } from "../../features/products/model/products.slice";
import {
  pushNotification,
  toggleOpen,
} from "../../features/notifications/model/notifications.slice";
import { logout } from "../../features/auth/model/auth.slice";
import { Sidebar } from "./Sidebar";
import AuditSummaryStrip from "./AuditSummaryStrip";
import { ShellHeaderNew, BreadcrumbStrip } from "./header";
import { RouteTracker } from "../router/RouteTracker";
import { AppRouter } from "../router/AppRouter";
import { useChordNavigation } from "../shortcuts/useChordNavigation";
import { ChordOverlay } from "../shortcuts/ChordOverlay";
import { MobileBottomBar } from "./MobileBottomBar";

/* ------------------------------------------------------------------ */
/*  ShellLayout — Main application layout with header, sidebar, routes */
/* ------------------------------------------------------------------ */

const ShellChrome: React.FC = () => {
  const { currentTheme } = useThemeContext();
  const colors = currentTheme.colors;
  const authState = useAppSelector((state) => state.auth);
  const { token, initialized } = authState;
  const showSidebar = Boolean(token);
  const location = useLocation();
  const { isBelow } = useBreakpoint();
  const isMobile = isBelow('md');
  const showAuditSummary =
    initialized && location.pathname.startsWith("/audit");
  const { isPending: chordPending, activeChords } = useChordNavigation();

  return (
    <div
      style={{
        background: colors.background,
        color: colors.text,
      }}
      className="flex min-h-screen flex-col"
    >
      {/* Fixed header */}
      <ShellHeaderNew />

      {/* Fixed sidebar — hidden on mobile (navigation in hamburger drawer) */}
      {showSidebar && !isMobile ? <Sidebar /> : null}

      {/* Main content area — offset by header height and sidebar width */}
      <div
        className="flex flex-1 flex-col"
        style={{
          paddingTop: 'var(--shell-header-h, 0px)',
          paddingLeft: showSidebar && !isMobile ? 'var(--shell-sidebar-w, 0px)' : undefined,
        }}
      >
        <BreadcrumbStrip showSidebar={showSidebar} maxItems={isMobile ? 3 : undefined} />
        {showAuditSummary ? <AuditSummaryStrip /> : null}
        <main
          className="flex min-h-0 flex-1 flex-col px-6 py-4"
          style={{ paddingBottom: isMobile && showSidebar ? '56px' : undefined }}
        >
          <AppRouter />
        </main>
      </div>

      {/* G-Chord overlay (desktop keyboard navigation) */}
      {!isMobile && <ChordOverlay isPending={chordPending} chords={activeChords} />}

      {/* Mobile bottom bar (authenticated only) */}
      {isMobile && showSidebar && <MobileBottomBar />}
    </div>
  );
};

export const ShellLayout: React.FC = () => {
  const dispatch = useAppDispatch();
  const authState = useAppSelector((state) => state.auth);
  const { token, expiresAt } = authState;
  const { t } = useShellCommonI18n();
  const {
    success: pushSuccessToast,
    info: pushInfoToast,
    warning: pushWarningToast,
    error: pushErrorToast,
  } = useToast();

  useShellShortcuts();

  /* Fetch initial data */
  useEffect(() => {
    dispatch(fetchProducts());
  }, [dispatch]);

  /* Runtime toast handler (custom events from remote modules) */
  const pushRuntimeToast = useCallback(
    (
      type: "success" | "info" | "warning" | "error" | "loading",
      message: string,
    ) => {
      const duration = type === "loading" ? 0 : 4500;
      if (type === "success") { pushSuccessToast(message, { duration }); return; }
      if (type === "warning") { pushWarningToast(message, { duration }); return; }
      if (type === "error") { pushErrorToast(message, { duration }); return; }
      // "loading" falls through to info since toast API has no loading variant
      pushInfoToast(message, { duration });
    },
    [pushErrorToast, pushInfoToast, pushSuccessToast, pushWarningToast],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleToast = (event: Event) => {
      const detail = (
        event as CustomEvent<
          { type?: string; text?: string; open?: boolean } | undefined
        >
      ).detail;
      const message =
        typeof detail?.text === "string" ? detail.text.trim() : "";
      if (!message) return;
      const type =
        detail?.type === "success" ||
        detail?.type === "info" ||
        detail?.type === "warning" ||
        detail?.type === "error" ||
        detail?.type === "loading"
          ? detail.type
          : "info";
      dispatch(
        pushNotification({
          message,
          type,
          priority:
            detail?.open === true || type === "warning" || type === "error"
              ? "high"
              : "normal",
          meta: { source: "app:toast", open: detail?.open === true },
        }),
      );
      pushRuntimeToast(type, message);
      if (detail?.open === true) {
        dispatch(toggleOpen(true));
      }
    };
    window.addEventListener("app:toast", handleToast as EventListener);
    return () => {
      window.removeEventListener("app:toast", handleToast as EventListener);
    };
  }, [dispatch, pushRuntimeToast]);

  /* Session expiry handler */
  useEffect(() => {
    if (!token || !expiresAt) return;
    const now = Date.now();
    const remaining = expiresAt - now;
    const sendSessionExpiredNotification = () => {
      dispatch(
        pushNotification({
          message: t("auth.session.expired"),
          description: t("auth.session.expired.description"),
          type: "warning",
          priority: "high",
          pinned: true,
          meta: { source: "session-expired" },
        }),
      );
    };
    if (remaining <= 0) {
      // Token expire oldu — Keycloak refresh yapacak (onTokenExpired handler).
      // Logout YAPMIYORUZ — refresh başarılı olursa kullanıcı fark etmez.
      if (process.env.NODE_ENV !== 'production') {
        console.debug('[SESSION] Token expired, Keycloak will refresh');
      }
      return;
    }
    const timeoutId = window.setTimeout(() => {
      // Token expire olacak — Keycloak refresh'e bırak, logout yapma.
      if (process.env.NODE_ENV !== 'production') {
        console.debug('[SESSION] Token expiry timer fired, Keycloak will refresh');
      }
    }, remaining);
    return () => window.clearTimeout(timeoutId);
  }, [dispatch, expiresAt, token, t]);

  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <RouteTracker />
      <ShellChrome />
    </BrowserRouter>
  );
};
