/** What the member list does to the table already on screen while it pages. */
import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { API } from '../../../test/handlers';
import { makeTestQueryClient } from '../../../test/render';
import { server } from '../../../test/server';
import { useMembers } from './api';

/** One member row, with only the fields these assertions read filled in. */
function memberPage(email: string) {
  return { count: 2, next: null, previous: null, results: [{ email }] };
}

/** One provider tree per test, so a cached page cannot leak between them. */
function makeWrapper() {
  const client = makeTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/** Answer page 1 with `one@example.org` and page 2 with `two@example.org`. */
function servePages(): void {
  server.use(
    http.get(`${API}/admin/members`, ({ request }) => {
      const page = new URL(request.url).searchParams.get('page');
      return HttpResponse.json(memberPage(page === '2' ? 'two@example.org' : 'one@example.org'));
    }),
  );
}

describe('useMembers', () => {
  it('holds the page already fetched on screen while the next one loads', async () => {
    servePages();

    const { result, rerender } = renderHook(({ page }) => useMembers({ page }), {
      wrapper: makeWrapper(),
      initialProps: { page: 1 },
    });
    await waitFor(() => expect(result.current.data?.results[0]?.email).toBe('one@example.org'));

    rerender({ page: 2 });

    expect(result.current.data?.results[0]?.email).toBe('one@example.org');
  });

  it('marks the page it is standing in for as placeholder data', async () => {
    servePages();

    const { result, rerender } = renderHook(({ page }) => useMembers({ page }), {
      wrapper: makeWrapper(),
      initialProps: { page: 1 },
    });
    await waitFor(() => expect(result.current.isPlaceholderData).toBe(false));

    rerender({ page: 2 });

    expect(result.current.isPlaceholderData).toBe(true);
  });

  it('shows the page that was asked for once it arrives', async () => {
    servePages();

    const { result, rerender } = renderHook(({ page }) => useMembers({ page }), {
      wrapper: makeWrapper(),
      initialProps: { page: 1 },
    });
    await waitFor(() => expect(result.current.data?.results[0]?.email).toBe('one@example.org'));

    rerender({ page: 2 });

    await waitFor(() => expect(result.current.data?.results[0]?.email).toBe('two@example.org'));
  });
});
