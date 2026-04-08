const readEnv = (keys: string[], fallback: string): string => {
  if (typeof process !== 'undefined' && process?.env) {
    for (const key of keys) {
      const value = process.env[key];
      if (typeof value === 'string' && value.length > 0) {
        return value;
      }
    }
  }
  if (typeof window !== 'undefined') {
    const scopedWindow = window as Window & { __env__?: Record<string, string> };
    for (const key of keys) {
      const value = scopedWindow.__env__?.[key];
      if (typeof value === 'string' && value.length > 0) {
        return value;
      }
    }
  }
  return fallback;
};

const readEnvBoolean = (keys: string[], fallback = false): boolean => {
  const value = readEnv(keys, fallback ? '1' : '');
  const normalized = value.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
};

export const isSuggestionsRemoteEnabled = (): boolean => (
  readEnvBoolean(['VITE_SHELL_ENABLE_SUGGESTIONS_REMOTE', 'SHELL_ENABLE_SUGGESTIONS_REMOTE'], true)
);

export const isEthicRemoteEnabled = (): boolean => (
  readEnvBoolean(['VITE_SHELL_ENABLE_ETHIC_REMOTE', 'SHELL_ENABLE_ETHIC_REMOTE'], true)
);
