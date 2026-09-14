/**
 * The single fetch wrapper the portal talks to Django through.
 *
 * - same-origin session cookies, so there is no token to store;
 * - CSRF fetched from `GET /api/v1/auth/csrf` whenever the `csrftoken` cookie is
 *   missing, then sent as `X-CSRFToken` on every unsafe method; a request the
 *   server refuses with a `CSRF Failed` 403 is retried once with a fresh token;
 * - JSON in, JSON out, and DRF error bodies surfaced as a typed `ApiError`.
 */

export const API_BASE = '/api/v1';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

const CSRF_COOKIE = 'csrftoken';

/** How DRF starts the `detail` of a 403 it raised before the view ran. */
const CSRF_FAILURE_PREFIX = 'CSRF Failed';

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

export interface EnsureCsrfOptions {
  /** Fetch a token even though a `csrftoken` cookie is already present. */
  force?: boolean;
}

/**
 * Make sure the browser holds a `csrftoken` cookie, fetching one if it does not.
 *
 * The cookie is the only cache: callers that arrive while a fetch is in flight share it,
 * and the promise is dropped as soon as it settles, so a failure is retried by the next
 * caller instead of locking the page out of every unsafe request.
 *
 * @throws ApiError when `GET /auth/csrf` answers a non-2xx status, and whatever `fetch`
 * rejects with when the request never reaches the server.
 */
export async function ensureCsrfToken(options: EnsureCsrfOptions = {}): Promise<void> {
  if (options.force !== true && readCookie(CSRF_COOKIE) !== null) return;
  csrfBootstrap ??= fetchCsrfCookie().finally(() => {
    csrfBootstrap = null;
  });
  await csrfBootstrap;
}

async function fetchCsrfCookie(): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/csrf`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseBody(response));
  }
}

/** Test seam: drop any bootstrap that is still in flight. */
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
  return text === '' ? null : text;
}

function isCsrfFailure(status: number, body: unknown): boolean {
  if (status !== 403) return false;
  if (body === null || typeof body !== 'object') return false;
  const detail = (body as Record<string, unknown>).detail;
  return typeof detail === 'string' && detail.startsWith(CSRF_FAILURE_PREFIX);
}

function send(path: string, method: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  };

  if (!SAFE_METHODS.has(method)) {
    const token = readCookie(CSRF_COOKIE);
    if (token !== null) headers['X-CSRFToken'] = token;
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

  return fetch(buildUrl(path, options.query), init);
}

/**
 * Issue a request and return its parsed JSON body, or `null` for a body-less 2xx.
 *
 * An unsafe method bootstraps the CSRF cookie first, and a `CSRF Failed` 403 is retried
 * exactly once against a freshly fetched token: the server rejected the request before
 * the view ran, so repeating it changes nothing else.
 *
 * @throws ApiError for any non-2xx response, carrying the status and the parsed body.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const isUnsafe = !SAFE_METHODS.has(method);
  if (isUnsafe) await ensureCsrfToken();

  const response = await send(path, method, options);
  if (response.ok) return (await parseBody(response)) as T;

  const body = await parseBody(response);
  if (!isUnsafe || !isCsrfFailure(response.status, body)) {
    throw new ApiError(response.status, body);
  }

  await ensureCsrfToken({ force: true });
  const retried = await send(path, method, options);
  if (retried.ok) return (await parseBody(retried)) as T;
  throw new ApiError(retried.status, await parseBody(retried));
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
