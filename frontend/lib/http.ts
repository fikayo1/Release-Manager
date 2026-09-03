// Transport helpers shared by the server-only API client. Kept free of
// `server-only` and `next/*` imports so the timeout and error-mapping
// behaviour is unit-testable in isolation.

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;
  constructor(status: number, detail?: string) {
    super(detail || `Release Manager API error (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export class UnauthorizedError extends ApiError {
  constructor(detail?: string) {
    super(401, detail || 'Authentication required');
    this.name = 'UnauthorizedError';
  }
}

export class ForbiddenError extends ApiError {
  constructor(detail?: string) {
    super(403, detail || 'You do not have access to that resource');
    this.name = 'ForbiddenError';
  }
}

export class RateLimitedError extends ApiError {
  constructor(detail?: string) {
    super(429, detail || 'Another scan is already running for your account');
    this.name = 'RateLimitedError';
  }
}

export class TimeoutError extends ApiError {
  constructor(detail?: string) {
    super(504, detail || 'The release service did not respond in time');
    this.name = 'TimeoutError';
  }
}

// Below C1's 10s budget: a hung backend rejects instead of suspending forever.
export const DEFAULT_TIMEOUT_MS = 8000;

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const body = await response.clone().json();
    if (body && typeof body.detail === 'string') return body.detail;
  } catch {
    /* non-JSON error body */
  }
  return undefined;
}

export async function fetchJson<T>(
  url: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new TimeoutError();
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const detail = await readDetail(response);
    if (response.status === 401) throw new UnauthorizedError(detail);
    if (response.status === 403) throw new ForbiddenError(detail);
    if (response.status === 429) throw new RateLimitedError(detail);
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}
