import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '../../test/handlers';
import { server } from '../../test/server';
import { ApiError, api, ensureCsrfToken, readCookie, request, resetCsrfBootstrap } from './client';

describe('ApiError', () => {
  it('reads DRF `detail` for its message', () => {
    const error = new ApiError(400, { detail: 'Incorrect email address or password.' });
    expect(error.message).toBe('Incorrect email address or password.');
  });

  it('falls back to a status-specific message', () => {
    expect(new ApiError(401, null).message).toMatch(/sign in/i);
    expect(new ApiError(403, null).message).toMatch(/permission/i);
    expect(new ApiError(404, null).message).toMatch(/not found/i);
    expect(new ApiError(500, null).message).toMatch(/500/);
  });

  it('exposes field errors for forms', () => {
    const error = new ApiError(400, {
      email: ['Enter a valid email address.'],
      password: 'Too short.',
      detail: 'Invalid.',
    });
    expect(error.fieldErrors).toEqual({
      email: 'Enter a valid email address.',
      password: 'Too short.',
    });
  });

  it('classifies 401 and 403', () => {
    expect(new ApiError(401, null).isUnauthenticated).toBe(true);
    expect(new ApiError(403, null).isForbidden).toBe(true);
    expect(new ApiError(403, null).isUnauthenticated).toBe(false);
  });
});

describe('request', () => {
  beforeEach(() => {
    resetCsrfBootstrap();
  });

  it('parses a JSON body', async () => {
    server.use(http.get(`${API}/thing`, () => HttpResponse.json({ ok: true })));
    await expect(request<{ ok: boolean }>('/thing')).resolves.toEqual({ ok: true });
  });

  it('returns null for 204', async () => {
    server.use(http.post(`${API}/thing`, () => new HttpResponse(null, { status: 204 })));
    await expect(api.post('/thing')).resolves.toBeNull();
  });

  it('throws ApiError with the parsed body on failure', async () => {
    server.use(
      http.get(`${API}/thing`, () => HttpResponse.json({ detail: 'Nope' }, { status: 403 })),
    );
    await expect(request('/thing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'Nope',
    });
  });

  it('sends same-origin credentials', async () => {
    let credentials: RequestCredentials | undefined;
    server.use(
      http.get(`${API}/thing`, ({ request: req }) => {
        credentials = req.credentials;
        return HttpResponse.json({});
      }),
    );
    await request('/thing');
    expect(credentials).toBe('same-origin');
  });

  it('bootstraps CSRF once and sends the header on unsafe methods', async () => {
    let csrfCalls = 0;
    let sentToken: string | null = null;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        document.cookie = 'csrftoken=abc123; path=/';
        return new HttpResponse(null, { status: 204 });
      }),
      http.post(`${API}/thing`, ({ request: req }) => {
        sentToken = req.headers.get('X-CSRFToken');
        return HttpResponse.json({ ok: true });
      }),
    );

    await api.post('/thing', { a: 1 });
    await api.post('/thing', { a: 2 });

    expect(csrfCalls).toBe(1);
    expect(sentToken).toBe('abc123');
  });

  it('does not fetch CSRF for GET', async () => {
    let csrfCalls = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
      http.get(`${API}/thing`, () => HttpResponse.json({})),
    );
    await api.get('/thing');
    expect(csrfCalls).toBe(0);
  });

  it('serializes a JSON body and sets the content type', async () => {
    let received: unknown;
    let contentType: string | null = null;
    server.use(
      http.post(`${API}/thing`, async ({ request: req }) => {
        contentType = req.headers.get('Content-Type');
        received = await req.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    await api.post('/thing', { email: 'a@b.test' });
    expect(received).toEqual({ email: 'a@b.test' });
    expect(contentType).toBe('application/json');
  });

  it('builds query strings and drops empty values', async () => {
    let url = '';
    server.use(
      http.get(`${API}/things`, ({ request: req }) => {
        url = req.url;
        return HttpResponse.json([]);
      }),
    );
    await api.get('/things', {
      query: { search: 'reyes', page: 2, dart: null, status: '', active: true },
    });
    const parsed = new URL(url);
    expect(parsed.searchParams.get('search')).toBe('reyes');
    expect(parsed.searchParams.get('page')).toBe('2');
    expect(parsed.searchParams.get('active')).toBe('true');
    expect(parsed.searchParams.has('dart')).toBe(false);
    expect(parsed.searchParams.has('status')).toBe(false);
  });

  it('supports every verb through the api helper', async () => {
    const seen: string[] = [];
    for (const method of ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']) {
      server.use(
        http.all(`${API}/verb`, ({ request: req }) => {
          seen.push(req.method);
          return HttpResponse.json({});
        }),
      );
      switch (method) {
        case 'GET':
          await api.get('/verb');
          break;
        case 'POST':
          await api.post('/verb', {});
          break;
        case 'PUT':
          await api.put('/verb', {});
          break;
        case 'PATCH':
          await api.patch('/verb', {});
          break;
        default:
          await api.delete('/verb');
      }
    }
    expect(seen).toEqual(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']);
  });
});

describe('readCookie / ensureCsrfToken', () => {
  beforeEach(() => resetCsrfBootstrap());

  it('reads and decodes a cookie', () => {
    document.cookie = 'csrftoken=tok%20en; path=/';
    expect(readCookie('csrftoken')).toBe('tok en');
    expect(readCookie('missing')).toBeNull();
  });

  it('skips the bootstrap when the cookie already exists', async () => {
    document.cookie = 'csrftoken=already; path=/';
    let calls = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await ensureCsrfToken();
    expect(calls).toBe(0);
  });
});
