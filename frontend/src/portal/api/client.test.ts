import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '../../test/handlers';
import { server } from '../../test/server';
import {
  ApiError,
  UnexpectedResponseError,
  api,
  ensureCsrfToken,
  readCookie,
  request,
  resetCsrfBootstrap,
} from './client';

/** A 204 that hands out `token`, exactly as `GET /auth/csrf` does. */
function csrfCookie(token: string): HttpResponse<null> {
  return new HttpResponse(null, {
    status: 204,
    headers: { 'Set-Cookie': `csrftoken=${token}; path=/` },
  });
}

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

  it('fetches again when forced, even though a cookie exists', async () => {
    document.cookie = 'csrftoken=stale; path=/';
    server.use(http.get(`${API}/auth/csrf`, () => csrfCookie('fresh')));
    await ensureCsrfToken({ force: true });
    expect(readCookie('csrftoken')).toBe('fresh');
  });
});

describe('CSRF bootstrap recovery', () => {
  beforeEach(() => resetCsrfBootstrap());

  it('rejects the request with the bootstrap failure rather than swallowing it', async () => {
    server.use(
      http.get(`${API}/auth/csrf`, () => HttpResponse.json({ detail: 'Down.' }, { status: 500 })),
      http.post(`${API}/thing`, () => HttpResponse.json({ ok: true })),
    );
    await expect(api.post('/thing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 500,
      message: 'Down.',
    });
  });

  it('fetches the cookie again after the bootstrap fails with a 500', async () => {
    let csrfCalls = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return csrfCalls === 1
          ? HttpResponse.json({ detail: 'Down.' }, { status: 500 })
          : csrfCookie('after-500');
      }),
      http.post(`${API}/thing`, () => HttpResponse.json({ ok: true })),
    );

    await expect(api.post('/thing')).rejects.toBeInstanceOf(ApiError);
    await expect(api.post('/thing')).resolves.toEqual({ ok: true });
    expect(csrfCalls).toBe(2);
  });

  it('sends the header on the request that follows a failed bootstrap', async () => {
    let csrfCalls = 0;
    let sentToken: string | null = null;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return csrfCalls === 1 ? HttpResponse.error() : csrfCookie('recovered');
      }),
      http.post(`${API}/thing`, ({ request: req }) => {
        sentToken = req.headers.get('X-CSRFToken');
        return HttpResponse.json({ ok: true });
      }),
    );

    await expect(api.post('/thing')).rejects.toThrow();
    await api.post('/thing');
    expect(sentToken).toBe('recovered');
  });

  it('fetches the cookie again when the bootstrap set no cookie', async () => {
    let csrfCalls = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
      http.post(`${API}/thing`, () => HttpResponse.json({ ok: true })),
    );

    await api.post('/thing');
    await api.post('/thing');
    expect(csrfCalls).toBe(2);
  });

  it('shares one bootstrap between concurrent requests', async () => {
    let csrfCalls = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return csrfCookie('shared');
      }),
      http.post(`${API}/thing`, () => HttpResponse.json({ ok: true })),
    );

    await Promise.all([api.post('/thing'), api.post('/thing')]);
    expect(csrfCalls).toBe(1);
  });

  it('retries once with a fresh token after a CSRF failure', async () => {
    let csrfCalls = 0;
    const tokensSent: (string | null)[] = [];
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return csrfCookie(`token-${csrfCalls}`);
      }),
      http.post(`${API}/thing`, ({ request: req }) => {
        tokensSent.push(req.headers.get('X-CSRFToken'));
        return tokensSent.length === 1
          ? HttpResponse.json({ detail: 'CSRF Failed: CSRF token missing.' }, { status: 403 })
          : HttpResponse.json({ ok: true });
      }),
    );

    await expect(api.post('/thing')).resolves.toEqual({ ok: true });
    expect(tokensSent).toEqual(['token-1', 'token-2']);
  });

  it('gives up after one retry when the fresh token is refused too', async () => {
    let posts = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => csrfCookie('never-good')),
      http.post(`${API}/thing`, () => {
        posts += 1;
        return HttpResponse.json({ detail: 'CSRF Failed: CSRF token incorrect.' }, { status: 403 });
      }),
    );

    await expect(api.post('/thing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'CSRF Failed: CSRF token incorrect.',
    });
    expect(posts).toBe(2);
  });

  it('does not retry a 403 that is not a CSRF failure', async () => {
    let posts = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => csrfCookie('good')),
      http.post(`${API}/thing`, () => {
        posts += 1;
        return HttpResponse.json({ detail: 'You do not have permission.' }, { status: 403 });
      }),
    );

    await expect(api.post('/thing')).rejects.toBeInstanceOf(ApiError);
    expect(posts).toBe(1);
  });

  it('hands a permission 403 back with the message the server sent', async () => {
    server.use(
      http.get(`${API}/auth/csrf`, () => csrfCookie('good')),
      http.post(`${API}/thing`, () =>
        HttpResponse.json(
          { detail: 'You do not have permission to perform this action.' },
          { status: 403 },
        ),
      ),
    );

    await expect(api.post('/thing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'You do not have permission to perform this action.',
    });
  });

  it('does not retry a CSRF failure on a safe method', async () => {
    let gets = 0;
    server.use(
      http.get(`${API}/thing`, () => {
        gets += 1;
        return HttpResponse.json(
          { detail: 'CSRF Failed: origin checking failed.' },
          { status: 403 },
        );
      }),
    );

    await expect(api.get('/thing')).rejects.toBeInstanceOf(ApiError);
    expect(gets).toBe(1);
  });
});

describe('the origins the client will talk to', () => {
  beforeEach(() => resetCsrfBootstrap());

  it('takes a bare path relative to the API base', async () => {
    let path = '';
    server.use(
      http.get(`${API}/thing`, ({ request: req }) => {
        path = new URL(req.url).pathname;
        return HttpResponse.json({ ok: true });
      }),
    );
    await request('/thing');
    expect(path).toBe('/api/v1/thing');
  });

  it('leaves a path that already carries the API base alone', async () => {
    let path = '';
    server.use(
      http.get(`${API}/thing`, ({ request: req }) => {
        path = new URL(req.url).pathname;
        return HttpResponse.json({ ok: true });
      }),
    );
    await request(`${API}/thing`);
    expect(path).toBe('/api/v1/thing');
  });

  it("accepts an absolute URL on the page's own origin", async () => {
    server.use(http.get(`${API}/thing`, () => HttpResponse.json({ ok: true })));
    await expect(request(`${window.location.origin}${API}/thing`)).resolves.toEqual({ ok: true });
  });

  it('refuses an absolute URL on another origin', async () => {
    await expect(request('https://evil.test/api/v1/thing')).rejects.toThrow(
      new TypeError(
        'Refusing to request https://evil.test/api/v1/thing: ' +
          'the API client only calls its own origin.',
      ),
    );
  });

  it('refuses a protocol-relative URL', async () => {
    await expect(api.post('//evil.test/api/v1/thing')).rejects.toThrow(
      new TypeError(
        'Refusing to request //evil.test/api/v1/thing: the API client only calls its own origin.',
      ),
    );
  });

  it('refuses a scheme that is not http at all', async () => {
    await expect(request('javascript:alert(1)')).rejects.toThrow(
      new TypeError(
        'Refusing to request javascript:alert(1): the API client only calls its own origin.',
      ),
    );
  });

  it('refuses a string that is not a URL once it looks absolute', async () => {
    await expect(request('http://')).rejects.toThrow(
      new TypeError('Refusing to request http://: it is not a usable URL.'),
    );
  });

  it('refuses the cross-origin request before any CSRF token is fetched', async () => {
    let csrfCalls = 0;
    server.use(
      http.get(`${API}/auth/csrf`, () => {
        csrfCalls += 1;
        return csrfCookie('leaked');
      }),
    );

    await expect(api.post('https://evil.test/collect', { a: 1 })).rejects.toBeInstanceOf(TypeError);
    expect(csrfCalls).toBe(0);
  });
});

describe('response bodies', () => {
  beforeEach(() => resetCsrfBootstrap());

  it('rejects a 2xx that is not JSON at all', async () => {
    server.use(
      http.get(
        `${API}/thing`,
        () =>
          new HttpResponse('<html><body>Down for maintenance</body></html>', {
            status: 200,
            headers: { 'Content-Type': 'text/html' },
          }),
      ),
    );
    await expect(request('/thing')).rejects.toBeInstanceOf(UnexpectedResponseError);
  });

  it('reports the status and content type it could not use', async () => {
    server.use(
      http.get(
        `${API}/thing`,
        () =>
          new HttpResponse('<html></html>', {
            status: 200,
            headers: { 'Content-Type': 'text/html; charset=utf-8' },
          }),
      ),
    );
    await expect(request('/thing')).rejects.toMatchObject({
      name: 'UnexpectedResponseError',
      status: 200,
      contentType: 'text/html; charset=utf-8',
    });
  });

  it('rejects a 2xx whose JSON body does not parse', async () => {
    server.use(
      http.get(
        `${API}/thing`,
        () =>
          new HttpResponse('{"results": [', {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    );
    await expect(request('/thing')).rejects.toBeInstanceOf(UnexpectedResponseError);
  });

  it('returns null for a 200 with an empty body', async () => {
    server.use(http.get(`${API}/thing`, () => new HttpResponse(null, { status: 200 })));
    await expect(request('/thing')).resolves.toBeNull();
  });

  it('still raises ApiError for an error page from a proxy', async () => {
    server.use(
      http.get(
        `${API}/thing`,
        () =>
          new HttpResponse('<html><body>502 Bad Gateway</body></html>', {
            status: 502,
            headers: { 'Content-Type': 'text/html' },
          }),
      ),
    );
    await expect(request('/thing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 502,
      message: 'Request failed (502).',
    });
  });
});
