import { render, renderHook, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider, useQuery } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';

import { ApiError } from './api/client';
import { createQueryClient } from './App';

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
