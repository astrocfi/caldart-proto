/**
 * The single fetch wrapper the portal talks to Django through.
 *
 * - same-origin session cookies, so there is no token to store; a request for any other
 *   origin is refused with a `TypeError` before it is sent;
 * - CSRF fetched from `GET /api/v1/auth/csrf` whenever the `csrftoken` cookie is
 *   missing, then sent as `X-CSRFToken` on every unsafe method; a request the
 *   server refuses with a `CSRF Failed` 403 is retried once with a fresh token;
 * - JSON in, JSON out: a non-2xx response becomes a typed `ApiError`, and a 2xx
 *   body that is neither empty nor JSON becomes an `UnexpectedResponseError`.
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

/**
 * A 2xx response whose body is not the JSON the caller was typed to expect.
 *
 * It carries no server message, so a screen that special-cases `ApiError` falls back to
 * its own copy, and the query client treats it like any other transport failure.
 */
export class UnexpectedResponseError extends Error {
  readonly status: number;
  readonly contentType: string | null;

  constructor(status: number, contentType: string | null, options?: ErrorOptions) {
    super('The server sent an unexpected response. Please try again.', options);
    this.name = 'UnexpectedResponseError';
    this.status = status;
    this.contentType = contentType;
  }
}

/** Read a cookie value by name, decoded, or `null` when it is not set or is empty. */
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
    throw new ApiError(response.status, await parseErrorBody(response));
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

/** A leading scheme, or the `//host` form, is what makes a string an absolute URL. */
const ABSOLUTE_URL = /^[a-z][a-z\d+\-.]*:|^\/\//i;

/**
 * Resolve `path` to a URL on the page's own origin.
 *
 * A path is read relative to `API_BASE` unless it already starts with it. An absolute
 * URL is accepted only when its origin is the page's own, because every request carries
 * the session cookie and, on an unsafe method, the `X-CSRFToken` header: neither may
 * ever be handed to another site.
 *
 * @throws TypeError when `path` looks absolute but is not a usable URL, or names an
 * origin other than the page's own.
 */
function resolveUrl(path: string): string {
  if (!ABSOLUTE_URL.test(path)) {
    return path.startsWith(API_BASE) ? path : `${API_BASE}${path}`;
  }

  let origin: string;
  try {
    origin = new URL(path, window.location.origin).origin;
  } catch {
    throw new TypeError(`Refusing to request ${path}: it is not a usable URL.`);
  }
  if (origin !== window.location.origin) {
    throw new TypeError(`Refusing to request ${path}: the API client only calls its own origin.`);
  }
  return path;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = resolveUrl(path);
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue;
    params.append(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}${url.includes('?') ? '&' : '?'}${qs}` : url;
}

/**
 * Read an error body as leniently as possible.
 *
 * Whatever a proxy or a crashed server puts in front of DRF still has to reach
 * `ApiError`, so a body that will not parse degrades to `null` rather than raising and
 * hiding the status the caller needs.
 */
async function parseErrorBody(response: Response): Promise<unknown> {
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

/**
 * Read a successful body, which must be JSON or nothing at all.
 *
 * Every body-less 2xx the API answers is a 204 with no `Content-Type`, so an empty body
 * is `null`. Anything else has to parse as JSON, because the caller's declared type says
 * it is JSON: an HTML maintenance page served with status 200 is a fault, not a value.
 *
 * @throws UnexpectedResponseError when the body is neither empty nor parseable JSON.
 */
async function parseSuccessBody(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const contentType = response.headers.get('content-type');
  const text = await response.text();
  if (text === '') return null;
  if (contentType === null || !contentType.includes('application/json')) {
    throw new UnexpectedResponseError(response.status, contentType);
  }
  try {
    return JSON.parse(text);
  } catch (cause) {
    throw new UnexpectedResponseError(response.status, contentType, { cause });
  }
}

function isCsrfFailure(status: number, body: unknown): boolean {
  if (status !== 403) return false;
  if (body === null || typeof body !== 'object') return false;
  const detail = (body as Record<string, unknown>).detail;
  return typeof detail === 'string' && detail.startsWith(CSRF_FAILURE_PREFIX);
}

function send(url: string, method: string, options: RequestOptions): Promise<Response> {
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

  return fetch(url, init);
}

/**
 * Issue a request and return its parsed JSON body, or `null` for a body-less 2xx.
 *
 * An unsafe method bootstraps the CSRF cookie first, and a `CSRF Failed` 403 is retried
 * exactly once against a freshly fetched token: the server rejected the request before
 * the view ran, so repeating it changes nothing else.
 *
 * The URL is resolved before anything else happens, so a caller that names another
 * origin is refused before a CSRF token is fetched or a cookie is sent.
 *
 * @throws TypeError when `path` names an origin other than the page's own.
 * @throws ApiError for any non-2xx response, carrying the status and the parsed body.
 * @throws UnexpectedResponseError for a 2xx body that is neither empty nor JSON.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const isUnsafe = !SAFE_METHODS.has(method);
  const url = buildUrl(path, options.query);
  if (isUnsafe) await ensureCsrfToken();

  const response = await send(url, method, options);
  if (response.ok) return (await parseSuccessBody(response)) as T;

  const body = await parseErrorBody(response);
  if (!isUnsafe || !isCsrfFailure(response.status, body)) {
    throw new ApiError(response.status, body);
  }

  await ensureCsrfToken({ force: true });
  const retried = await send(url, method, options);
  if (retried.ok) return (await parseSuccessBody(retried)) as T;
  throw new ApiError(retried.status, await parseErrorBody(retried));
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> => request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> => request<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> => request<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> =>
    request<T>(path, { ...options, method: 'DELETE' }),
};
