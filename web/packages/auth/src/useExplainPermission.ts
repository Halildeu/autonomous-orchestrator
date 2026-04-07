import { useCallback, useState } from 'react';
import type { ExplainResponse } from './types';

interface UseExplainPermissionOptions {
  httpPost: (url: string, body: any) => Promise<{ data: any }>;
}

/**
 * Server-side permission explain — calls POST /v1/authz/explain.
 * Returns full details: reason, source role, user roles, scopes.
 */
export function useExplainPermission({ httpPost }: UseExplainPermissionOptions) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExplainResponse | null>(null);

  const explain = useCallback(async (userId: string, permissionType: string, permissionKey: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await httpPost('/api/v1/authz/explain', { userId, permissionType, permissionKey });
      const data = res.data as ExplainResponse;
      setResult(data);
      return data;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Explain request failed';
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [httpPost]);

  return { explain, result, loading, error };
}
