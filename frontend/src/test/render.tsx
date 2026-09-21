/** Test helpers: render a component inside the portal's providers + router. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { RenderOptions, RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter, RouterProvider, createMemoryRouter } from 'react-router-dom';
import type { RouteObject } from 'react-router-dom';

import { ToastProvider } from '../portal/components/Toast';

/** A TanStack Query client with retries and caching turned off, for deterministic tests. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string;
  client?: QueryClient;
}

function Providers({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

/**
 * Render `ui` under the query client, the toast queue and a `MemoryRouter`
 * started at `route`.  The caller's own `<Routes>` decide what the router shows.
 */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/', client, ...options }: RenderWithProvidersOptions = {},
): RenderResult & { client: QueryClient } {
  const queryClient = client ?? makeTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <Providers client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </Providers>
    );
  }

  return { ...render(ui, { wrapper: Wrapper, ...options }), client: queryClient };
}

export type TestRouter = ReturnType<typeof createMemoryRouter>;

export interface RenderRoutesOptions {
  route?: string;
  client?: QueryClient;
}

/**
 * Render a whole route table through a data router started at `route`.
 *
 * `renderWithProviders` mounts one component under a plain `MemoryRouter`;
 * this mounts the routes themselves, so the layout, the guards and route
 * properties such as `lazy` all take part.  The returned `router` carries the
 * location, which is how a test reads a redirect.
 */
export function renderRoutes(
  routes: RouteObject[],
  { route = '/', client }: RenderRoutesOptions = {},
): RenderResult & { client: QueryClient; router: TestRouter } {
  const queryClient = client ?? makeTestQueryClient();
  const router = createMemoryRouter(routes, { initialEntries: [route] });

  return {
    ...render(
      <Providers client={queryClient}>
        <RouterProvider router={router} />
      </Providers>,
    ),
    client: queryClient,
    router,
  };
}
