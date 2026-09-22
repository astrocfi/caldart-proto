/** What the aircraft register does to the rows already on screen while it pages and filters. */
import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { makeTestQueryClient } from '@test/render';
import { server } from '@test/server';
import { useAircraftList } from './api';

/** One register row, with only the field these assertions read filled in. */
function aircraftPage(nNumber: string) {
  return { count: 2, next: null, previous: null, results: [{ n_number: nNumber }] };
}

/** One provider tree per test, so a cached page cannot leak between them. */
function makeWrapper() {
  const client = makeTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/** Answer page 1 with `N12345` and page 2 with `N54321`. */
function servePages(): void {
  server.use(
    http.get(`${API}/aircraft`, ({ request }) => {
      const page = new URL(request.url).searchParams.get('page');
      return HttpResponse.json(aircraftPage(page === '2' ? 'N54321' : 'N12345'));
    }),
  );
}

/** Answer an unfiltered register with `N12345` and any search with `N54321`. */
function serveSearches(): void {
  server.use(
    http.get(`${API}/aircraft`, ({ request }) => {
      const search = new URL(request.url).searchParams.get('search');
      return HttpResponse.json(aircraftPage(search === null ? 'N12345' : 'N54321'));
    }),
  );
}

describe('useAircraftList', () => {
  it('holds the page already fetched on screen while the next one loads', async () => {
    servePages();

    const { result, rerender } = renderHook(({ page }) => useAircraftList({ page }), {
      wrapper: makeWrapper(),
      initialProps: { page: 1 },
    });
    await waitFor(() => expect(result.current.data?.results[0]?.n_number).toBe('N12345'));

    rerender({ page: 2 });

    expect(result.current.data?.results[0]?.n_number).toBe('N12345');
  });

  it('holds the rows already fetched on screen while a changed filter loads', async () => {
    serveSearches();

    const { result, rerender } = renderHook(({ search }) => useAircraftList({ search }), {
      wrapper: makeWrapper(),
      initialProps: { search: '' },
    });
    await waitFor(() => expect(result.current.data?.results[0]?.n_number).toBe('N12345'));

    rerender({ search: 'N543' });

    expect(result.current.data?.results[0]?.n_number).toBe('N12345');
  });

  it('shows the rows the changed filter asked for once they arrive', async () => {
    serveSearches();

    const { result, rerender } = renderHook(({ search }) => useAircraftList({ search }), {
      wrapper: makeWrapper(),
      initialProps: { search: '' },
    });
    await waitFor(() => expect(result.current.data?.results[0]?.n_number).toBe('N12345'));

    rerender({ search: 'N543' });

    await waitFor(() => expect(result.current.data?.results[0]?.n_number).toBe('N54321'));
  });

  it('marks the page it is standing in for as placeholder data', async () => {
    servePages();

    const { result, rerender } = renderHook(({ page }) => useAircraftList({ page }), {
      wrapper: makeWrapper(),
      initialProps: { page: 1 },
    });
    await waitFor(() => expect(result.current.isPlaceholderData).toBe(false));

    rerender({ page: 2 });

    expect(result.current.isPlaceholderData).toBe(true);
  });

  it('shows the page that was asked for once it arrives', async () => {
    servePages();

    const { result, rerender } = renderHook(({ page }) => useAircraftList({ page }), {
      wrapper: makeWrapper(),
      initialProps: { page: 1 },
    });
    await waitFor(() => expect(result.current.data?.results[0]?.n_number).toBe('N12345'));

    rerender({ page: 2 });

    await waitFor(() => expect(result.current.data?.results[0]?.n_number).toBe('N54321'));
  });
});
