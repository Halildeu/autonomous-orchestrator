import type { ShellNotificationEntry, ShellNotificationType } from 'mfe_shell/services';
import { getShellServices } from '../app/services/shell-services';

type ToastOptions = {
  description?: string;
  meta?: Record<string, unknown>;
  openInCenter?: boolean;
};

const dispatchWindowToast = (type: ShellNotificationType, text: string) => {
  try {
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { type, text } }));
  } catch {
    if (process.env.NODE_ENV !== 'production') {
      const method = type === 'error' ? 'error' : 'log';
      console[method](text);
    }
  }
};

export const pushToast = (
  type: ShellNotificationType,
  message: string,
  options?: ToastOptions,
) => {
  const entry: ShellNotificationEntry = {
    message,
    description: options?.description,
    type,
    meta: options?.meta ? { ...options.meta } : undefined,
  };
  if (options?.openInCenter) {
    entry.meta = { ...(entry.meta ?? {}), open: true };
  }

  try {
    const services = getShellServices();
    services.notify.push(entry);
    return;
  } catch {
    // Shell servisleri henüz enjekte edilmediyse window event fallback'ini kullan.
  }
  dispatchWindowToast(type, message);
};
