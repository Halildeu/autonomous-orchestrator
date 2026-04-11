import type {
  AuthzMeResponse,
  CheckRequest,
  CheckResponse,
  BatchCheckRequest,
  BatchCheckResponse,
  BatchCheckItem,
} from './types';

/**
 * Fetch current user's authorization context from backend.
 * Backend proxies to OpenFGA; in dev/permitAll mode returns dev defaults.
 * Retries up to 2 times on 5xx errors (Hibernate session race condition).
 */
export async function fetchAuthzMe(
  httpGet: (url: string) => Promise<{ data: AuthzMeResponse }>
): Promise<AuthzMeResponse> {
  const MAX_RETRIES = 2;
  let lastError: unknown;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const { data } = await httpGet('/v1/authz/me');
      return data;
    } catch (err: unknown) {
      lastError = err;
      const status = (err as { response?: { status?: number } })?.response?.status;
      // Only retry on server errors (5xx), not auth errors (4xx)
      if (!status || status < 500 || attempt === MAX_RETRIES) {
        throw err;
      }
      // Wait before retry: 500ms, then 1000ms
      await new Promise(r => setTimeout(r, (attempt + 1) * 500));
    }
  }

  throw lastError;
}

/**
 * Lightweight version check for cache invalidation polling.
 * Frontend calls this instead of full /me to detect permission changes.
 */
export async function fetchAuthzVersion(
  httpGet: (url: string) => Promise<{ data: { authzVersion: number } }>
): Promise<number> {
  try {
    const { data } = await httpGet('/v1/authz/version');
    return data.authzVersion;
  } catch {
    return -1;
  }
}

/**
 * Point authorization check via backend proxy.
 * CNS-20260411-005: Returns full CheckResponse with reason (not just boolean).
 */
export async function checkPermission(
  httpPost: (url: string, body: CheckRequest) => Promise<{ data: CheckResponse }>,
  request: CheckRequest
): Promise<CheckResponse> {
  const { data } = await httpPost('/v1/authz/check', request);
  return data;
}

/**
 * Batch authorization check — multiple object-level checks in a single request.
 * CNS-20260411-005: Codex REJECT (without batch) — max 20 per call.
 */
export async function checkPermissionBatch(
  httpPost: (url: string, body: BatchCheckRequest) => Promise<{ data: BatchCheckResponse }>,
  checks: CheckRequest[]
): Promise<BatchCheckItem[]> {
  const { data } = await httpPost('/v1/authz/batch-check', { checks });
  return data.results;
}
