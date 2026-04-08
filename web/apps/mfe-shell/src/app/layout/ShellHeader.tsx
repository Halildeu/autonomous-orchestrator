import React, { useEffect, useMemo, useCallback, useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LayoutGrid, ChevronDown } from "lucide-react";
import { ShellHeader as ShellHeaderPattern } from "@mfe/design-system";
import type { ShellHeaderNavItem } from "@mfe/design-system";
import { useAppDispatch, useAppSelector } from "../store/store.hooks";
import { buildAppRedirectUri, isPermitAllMode } from "../auth/auth-config";
import keycloak from "../auth/keycloakClient";
import { logout } from "../../features/auth/model/auth.slice";
import { usePermissions } from "@mfe/auth";
import { MODULE_KEYS } from "../../features/auth/lib/permissions.constants";
import {
  isSuggestionsRemoteEnabled,
  isEthicRemoteEnabled,
} from "../shell-navigation";
import { useShellCommonI18n } from "../i18n";
import { DesignLabHeaderMenu } from "./DesignLabHeaderMenu";
import NotificationCenter from "./NotificationCenter";
import SessionAuditShortcutsMenu from "./SessionAuditShortcutsMenu";
import LoginPopover from "./LoginPopover";
import AppLauncher from "./AppLauncher";
import { ThemeRuntimePanelButton } from "./ThemeRuntimePanelButton";
import { UserMenuPopover } from "./UserMenuPopover";

/* ------------------------------------------------------------------ */
/*  ShellHeader — Top navigation bar                                   */
/* ------------------------------------------------------------------ */

export const ShellHeader: React.FC = () => {
  const { token, user, initialized } = useAppSelector((state) => state.auth);
  const dispatch = useAppDispatch();
  const location = useLocation();
  const navigate = useNavigate();
  const [loginOpen, setLoginOpen] = useState(false);
  const [launcherOpen, setLauncherOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { hasModule, isSuperAdmin } = usePermissions();
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  const { t, manager: i18nManager, locale } = useShellCommonI18n();
  const permitAllMode = isPermitAllMode();

  const suggestionsEnabled = isSuggestionsRemoteEnabled();
  const ethicEnabled = isEthicRemoteEnabled();
  const sa = isSuperAdmin();
  const canAccess = initialized && (sa || hasModule(MODULE_KEYS.ACCESS));
  const canAudit = initialized && (sa || hasModule(MODULE_KEYS.AUDIT));
  const canReport = initialized && (sa || hasModule(MODULE_KEYS.REPORT));
  const canManageUsers = initialized && (sa || hasModule(MODULE_KEYS.USER_MANAGEMENT));
  const canThemeAdmin = initialized && (sa || hasModule(MODULE_KEYS.THEME));

  useEffect(() => {
    setLoginOpen(false);
    setLauncherOpen(false);
    setUserMenuOpen(false);
  }, [location.pathname]);

  /* ---- Nav items ---- */
  const navItems: ShellHeaderNavItem[] = useMemo(() => {
    const items: ShellHeaderNavItem[] = [
      { key: "/", path: "/", label: t("shell.nav.home") },
    ];
    if (suggestionsEnabled) items.push({ key: "/suggestions", path: "/suggestions", label: t("shell.nav.suggestions") });
    if (ethicEnabled) items.push({ key: "/ethic", path: "/ethic", label: t("shell.nav.ethic") });
    if (canAccess) items.push({ key: "/access", path: "/access/roles", label: t("shell.nav.access") });
    if (canAudit) items.push({ key: "/audit", path: "/audit/events", label: t("shell.nav.audit") });
    if (canReport) items.push({ key: "/admin/reports", path: "/admin/reports", label: t("shell.nav.reports") });
    if (canManageUsers) items.push({ key: "/admin/users", path: "/admin/users", label: t("shell.nav.users") });
    if (canThemeAdmin) items.push({ key: "/admin/themes", path: "/admin/themes", label: t("shell.nav.themes") });
    items.push({ key: "/admin/services", path: "/admin/services", label: t("shell.nav.services") });
    items.push({ key: "/admin/schema-explorer", path: "/admin/schema-explorer", label: t("shell.nav.schemaExplorer") });
    return items;
  }, [canAccess, canAudit, canManageUsers, canReport, canThemeAdmin, ethicEnabled, suggestionsEnabled, t]);

  /* ---- User display ---- */
  const userDisplayName = useMemo(() => {
    if (user?.fullName?.trim()) return user.fullName;
    if (user?.displayName) return user.displayName;
    if (user?.name) return user.name;
    if (user?.email) return user.email.split("@")[0];
    return t("shell.header.defaultUser");
  }, [t, locale, user?.displayName, user?.email, user?.fullName, user?.name]);

  const formattedLastLogin = useMemo(() => {
    if (!user?.lastLoginAt) return t("shell.header.neverLoggedIn");
    try {
      const date = new Date(user.lastLoginAt);
      const localeMap: Record<string, string> = { tr: "tr-TR", en: "en-US", de: "de-DE", es: "es-ES" };
      return date.toLocaleString(localeMap[locale] ?? undefined);
    } catch { return user.lastLoginAt; }
  }, [user?.lastLoginAt, t, locale]);

  const userMenuItems = useMemo(() => [
    { key: "last-login", label: t("shell.header.lastLogin").replace("{value}", formattedLastLogin), disabled: true },
    { type: "divider" as const },
    { key: "profile", label: t("shell.header.profileSoon"), disabled: true },
    { type: "divider" as const },
    { key: "logout", label: t("shell.header.logout"), icon: "🚪" },
  ], [formattedLastLogin, t]);

  const handleLogout = useCallback(() => {
    dispatch(logout());
    if (typeof window !== "undefined") {
      keycloak.logout({ redirectUri: buildAppRedirectUri("/login"), federated: true }).catch(() => {});
    }
  }, [dispatch]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) setUserMenuOpen(false);
    };
    window.addEventListener("click", handleClickOutside);
    return () => window.removeEventListener("click", handleClickOutside);
  }, []);

  /* ---- Slots ---- */
  const startSlot = (
    <button
      type="button"
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-action-secondary-border bg-action-secondary text-action-secondary-text shadow-xs transition hover:opacity-90"
      onClick={() => setLauncherOpen((prev) => !prev)}
      aria-label={t("shell.launcher.title")}
      title={t("shell.launcher.title")}
    >
      <LayoutGrid className="h-4 w-4" aria-hidden />
    </button>
  );

  const sessionAuditShortcutEnabled = Boolean(token && user?.email && canAudit);

  const endSlot = (
    <>
      {/* Language selector */}
      <div className="hidden items-center gap-2 xl:flex">
        <span className="hidden text-xs font-semibold text-text-secondary md:inline">
          {t("shell.header.language")}:
        </span>
        <select
          className="h-8 rounded-md border border-action-secondary-border bg-action-secondary px-2 text-xs font-semibold text-action-secondary-text focus:outline-hidden focus:ring-2 focus:ring-selection-outline focus:ring-offset-1"
          value={i18nManager.getLocale()}
          aria-label={t("shell.header.languageSelectAria")}
          onChange={(event) => {
            const nextLocale = event.target.value;
            i18nManager.setLocale(nextLocale);
            try {
              window.localStorage.setItem("mfe.locale", nextLocale);
              window.dispatchEvent(new CustomEvent("app:locale-change", { detail: { locale: nextLocale } }));
            } catch { /* intentionally empty */ }
          }}
        >
          <option value="tr">🇹🇷 {t("shell.language.tr")}</option>
          <option value="en">🇬🇧 {t("shell.language.en")}</option>
          <option value="de">🇩🇪 {t("shell.language.de")}</option>
          <option value="es">🇪🇸 {t("shell.language.es")}</option>
        </select>
      </div>
      <div className="inline-flex items-center rounded-full border border-border-subtle bg-surface-panel px-2 py-1 text-xs font-semibold text-text-secondary xl:hidden">
        <span aria-hidden>
          {locale === "tr" ? "🇹🇷" : locale === "en" ? "🇬🇧" : locale === "de" ? "🇩🇪" : locale === "es" ? "🇪🇸" : "🌐"}
        </span>
      </div>
      <div className="inline-flex">
        <ThemeRuntimePanelButton />
      </div>
      {sessionAuditShortcutEnabled && (
        <SessionAuditShortcutsMenu email={user?.email} label={t("shell.nav.audit")} />
      )}
      <NotificationCenter />
      {token ? (
        <div className="relative" ref={userMenuRef}>
          <button
            type="button"
            onClick={(event) => { event.preventDefault(); event.stopPropagation(); setUserMenuOpen((prev) => !prev); }}
            className="inline-flex items-center gap-1 rounded-full border border-border-subtle bg-surface-panel px-2.5 py-1.5 text-xs font-medium text-text-primary hover:bg-surface-muted lg:gap-2 lg:px-3"
          >
            <span aria-hidden>👤</span>
            <span className="max-w-[140px] truncate text-left hidden lg:inline">{userDisplayName}</span>
            <ChevronDown className="h-3 w-3" aria-hidden />
          </button>
          {userMenuOpen && <UserMenuPopover onClose={() => setUserMenuOpen(false)} onLogout={handleLogout} items={userMenuItems} />}
        </div>
      ) : permitAllMode ? (
        <span className="rounded-full border border-border-subtle bg-surface-panel px-3 py-1 text-xs font-semibold text-text-secondary">
          {t("shell.header.permitAllNoLogin")}
        </span>
      ) : (
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-full border border-action-primary-border bg-action-primary px-4 py-2 text-xs font-semibold text-action-primary-text shadow-xs hover:opacity-90"
          onClick={() => {
            setLoginOpen(false);
            keycloak.login({ redirectUri: buildAppRedirectUri(window.location.href) }).catch(() => { setLoginOpen(true); });
          }}
        >
          <span aria-hidden>🔑</span>
          <span>{t("shell.header.loginPanel")}</span>
        </button>
      )}
    </>
  );

  return (
    <>
      <ShellHeaderPattern
        navItems={navItems}
        currentPath={location.pathname}
        onNavigate={(path) => { if (path !== location.pathname) navigate(path); }}
        startSlot={startSlot}
        endSlot={endSlot}
        menuUtility={canThemeAdmin ? <DesignLabHeaderMenu /> : undefined}
        navAriaLabel={locale === "tr" ? "Ana gezinme" : "Primary navigation"}
        overflowLabel={t("shell.nav.morePages")}
        cssHeightVar="--shell-header-h"
      />
      {!token && !permitAllMode && loginOpen && (
        <LoginPopover onClose={() => setLoginOpen(false)} onNavigate={() => navigate("/login")} />
      )}
      {launcherOpen && <AppLauncher onClose={() => setLauncherOpen(false)} />}
    </>
  );
};
