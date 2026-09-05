/**
 * The single fetch wrapper the portal talks to Django through (PLAN §8).
 *
 * - same-origin session cookies, so there is no token to store;
 * - CSRF bootstrapped once from `GET /api/v1/auth/csrf`, then sent as
 *   `X-CSRFToken` on every unsafe method;
 * - JSON in, JSON out, and DRF error bodies surfaced as a typed `ApiError`.
 */

export const API_BASE = '/api/v1';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

/** A non-2xx response, with the DRF error body attached. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? ApiError.messageFor(status, body));
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }

  static messageFor(status: number, body: unknown): string {
    const detail = ApiError.readDetail(body);
    if (detail) return detail;
    if (status === 401) return 'You need to sign in to do that.';
    if (status === 403) return 'You do not have permission to do that.';
    if (status === 404) return 'Not found.';
    return `Request failed (${status}).`;
  }

  private static readDetail(body: unknown): string | null {
    if (!body || typeof body !== 'object') return null;
    const record = body as Record<string, unknown>;
    if (typeof record.detail === 'string') return record.detail;
    for (const value of Object.values(record)) {
      if (typeof value === 'string') return value;
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
    }
    return null;
  }

  /** Field-keyed validation messages, for wiring straight into a form. */
  get fieldErrors(): Record<string, string> {
    if (!this.body || typeof this.body !== 'object') return {};
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(this.body as Record<string, unknown>)) {
      if (key === 'detail') continue;
      if (typeof value === 'string') out[key] = value;
      else if (Array.isArray(value) && typeof value[0] === 'string') out[key] = value[0];
    }
    return out;
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }
}

export function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

let csrfBootstrap: Promise<void> | null = null;

/** Fetch the CSRF cookie once per page load. */
export async function ensureCsrfToken(): Promise<void> {
  if (readCookie('csrftoken')) return;
  csrfBootstrap ??= fetch(`${API_BASE}/auth/csrf`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  }).then(
    () => undefined,
    () => undefined,
  );
  await csrfBootstrap;
}

/** Test seam: forget that CSRF was already bootstrapped. */
export function resetCsrfBootstrap(): void {
  csrfBootstrap = null;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = path.startsWith('http') || path.startsWith(API_BASE) ? path : `${API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue;
    params.append(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}${url.includes('?') ? '&' : '?'}${qs}` : url;
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const type = response.headers.get('content-type') ?? '';
  if (type.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  const text = await response.text();
  return text || null;
}

/** Issue a request and return the parsed JSON body, or throw `ApiError`. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  };

  if (!SAFE_METHODS.has(method)) {
    await ensureCsrfToken();
    const token = readCookie('csrftoken');
    if (token) headers['X-CSRFToken'] = token;
  }

  let payload: BodyInit | undefined;
  if (options.body !== undefined) {
    if (options.body instanceof FormData) {
      payload = options.body;
    } else {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(options.body);
    }
  }

  const init: RequestInit = {
    method,
    credentials: 'same-origin',
    headers,
  };
  if (payload !== undefined) init.body = payload;
  if (options.signal) init.signal = options.signal;

  const response = await fetch(buildUrl(path, options.query), init);
  const body = await parseBody(response);

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    request<T>(path, { ...options, method: 'DELETE' }),
};
