import type { LucideIcon } from 'lucide-react';
import { Home, Users, BarChart3, Server, Shield, Palette } from 'lucide-react';
import { MODULE_KEYS } from '../../features/auth/lib/permissions.constants';

/* ------------------------------------------------------------------ */
/*  G-Chord Navigation — Linear-style "g then key" shortcuts           */
/* ------------------------------------------------------------------ */

export interface ChordEntry {
  /** Second keystroke (lowercase) */
  key: string;
  /** i18n key for the destination label */
  labelKey: string;
  /** Route to navigate to */
  path: string;
  /** Icon shown in the chord overlay */
  icon: LucideIcon;
  /** Optional permission check */
  permission?: string;
}

/** Timeout in ms before the chord state resets to idle */
export const CHORD_TIMEOUT_MS = 1500;

export const CHORD_MAP: ChordEntry[] = [
  { key: 'h', labelKey: 'shell.chord.home', path: '/', icon: Home },
  { key: 'u', labelKey: 'shell.chord.users', path: '/admin/users', icon: Users, permission: MODULE_KEYS.USER_MANAGEMENT },
  { key: 'r', labelKey: 'shell.chord.reports', path: '/admin/reports', icon: BarChart3 },
  { key: 's', labelKey: 'shell.chord.services', path: '/admin/services', icon: Server },
  { key: 'a', labelKey: 'shell.chord.audit', path: '/audit/events', icon: Shield, permission: MODULE_KEYS.AUDIT },
  { key: 't', labelKey: 'shell.chord.themes', path: '/admin/themes', icon: Palette, permission: MODULE_KEYS.THEME },
];
