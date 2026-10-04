import { render, renderHook, screen, waitFor } from '@testing-library/react';
import { matchRoutes } from 'react-router-dom';
import { QueryClientProvider, useQuery } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';

import { ApiError } from './api/client';
import { createQueryClient } from './App';
import { NAV_ITEMS } from './nav';
import { routes } from './routes';

/** Run `queryFn` under the application's real query client. */
function runQuery(client: QueryClient, queryFn: () => Promise<string>) {
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return renderHook(() => useQuery({ queryKey: ['subject'], queryFn, retryDelay: 0 }), {
    wrapper,
  });
}

describe('the router', () => {
  afterEach(() => {
    clearUrlPrefix();
    window.history.replaceState(null, '', '/');
  });

  it('routes under the basename the page is served under', async () => {
    stampUrlPrefix('/x');
    window.history.replaceState(null, '', '/x/portal/login');
    const { App } = await import('./App');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('routes under /portal when the page carries no prefix', async () => {
    clearUrlPrefix();
    window.history.replaceState(null, '', '/portal/login');
    const { App } = await import('./App');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});

/** The catch-all route's path, which renders the not-found page. */
const NOT_FOUND = '*';

/**
 * The path of the route the portal's router renders for `pathname`: the deepest match,
 * `index` for an index route, or the catch-all when nothing matches.
 */
function screenRoute(pathname: string): string {
  const deepest = matchRoutes(routes, pathname)?.at(-1)?.route;
  if (deepest === undefined) return NOT_FOUND;
  return deepest.path ?? (deepest.index === true ? 'index' : '');
}

/** The rail's Bulk Email entries and every entry open to any signed-in member. */
const BULK_AND_MEMBER_ENTRIES = NAV_ITEMS.filter(
  (item) => item.group === 'Bulk Email' || item.roles.length === 0,
).map((item) => [item.label, item.to]);

describe('the rail and the router', () => {
  it('covers every Bulk Email entry and every member-facing entry', () => {
    expect(BULK_AND_MEMBER_ENTRIES.map(([label]) => label)).toEqual([
      'Dashboard',
      'My profile',
      'My aircraft',
      'Payments',
      'Donate',
      'Renew',
      'Change password',
      'Change email',
      'Compose',
      'Drafts & scheduled',
      'Sent',
      'Templates',
      'Recipient groups',
      'Callouts',
      'Email types',
      'Mail delivery',
      'Messages',
      'Email preferences',
    ]);
  });

  it.each(BULK_AND_MEMBER_ENTRIES)(
    'routes %s (%s) to a screen, never the not-found page',
    (_label, to) => {
      expect(screenRoute(to ?? '')).not.toBe(NOT_FOUND);
    },
  );

  it('routes each of those entries to a different screen', () => {
    const screens = BULK_AND_MEMBER_ENTRIES.map(([, to]) => screenRoute(to ?? ''));
    expect(new Set(screens).size).toBe(BULK_AND_MEMBER_ENTRIES.length);
  });

  it('reads an unknown path as the not-found page, so the cases above can fail', () => {
    expect(screenRoute('/not-a-real-screen')).toBe(NOT_FOUND);
  });
});

describe('createQueryClient', () => {
  it('keeps a fetched answer fresh for thirty seconds', () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.queries?.staleTime).toBe(30_000);
  });

  it('does not refetch when the window regains focus', () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
  });

  it('never retries a mutation, because a second POST is a second payment', () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.mutations?.retry).toBe(false);
  });

  it.each([400, 401, 403, 404, 409, 422, 499])(
    'gives up immediately on a %d, because asking again will not help',
    async (status) => {
      const queryFn = vi.fn(() => Promise.reject(new ApiError(status, { detail: 'No.' })));

      const { result } = runQuery(createQueryClient(), queryFn);

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(queryFn).toHaveBeenCalledTimes(1);
    },
  );

  it.each([500, 502, 503])('retries a %d twice before failing', async (status) => {
    const queryFn = vi.fn(() => Promise.reject(new ApiError(status, null)));

    const { result } = runQuery(createQueryClient(), queryFn);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(queryFn).toHaveBeenCalledTimes(3);
  });

  it('retries a transport failure that is not an ApiError at all', async () => {
    const queryFn = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')));

    const { result } = runQuery(createQueryClient(), queryFn);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(queryFn).toHaveBeenCalledTimes(3);
  });

  it('stops retrying as soon as an attempt succeeds', async () => {
    let attempts = 0;
    const queryFn = vi.fn(() => {
      attempts += 1;
      if (attempts === 1) return Promise.reject(new ApiError(503, null));
      return Promise.resolve('settled');
    });

    const { result } = runQuery(createQueryClient(), queryFn);

    await waitFor(() => expect(result.current.data).toBe('settled'));
    expect(queryFn).toHaveBeenCalledTimes(2);
  });
});
