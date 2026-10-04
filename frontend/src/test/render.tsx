/** Test helpers: render a component inside the portal's providers + router. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { RenderOptions, RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter, RouterProvider, createMemoryRouter } from 'react-router-dom';
import type { RouteObject } from 'react-router-dom';
import { vi } from 'vitest';

import type { RoleSlug } from '../portal/api/types';
import { AUTH_ME_KEY } from '../portal/auth/useAuth';
import { ToastProvider } from '../portal/components/Toast';
import { makeUser, signedInAs } from './handlers';
import { server } from './server';

/** A TanStack Query client with retries and caching turned off, for deterministic tests. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

/**
 * A test query client already holding a signed-in user with the member role and `roles`,
 * with `/auth/me` answering the same user.
 *
 * The user is in the cache before the first render, so a screen reads its roles at once
 * and a test asserting that a control is absent for those roles cannot pass merely
 * because `/auth/me` had not answered yet.
 */
export function signedInClient(...roles: RoleSlug[]): QueryClient {
  const user = makeUser({ roles: ['member', ...roles] });
  server.use(signedInAs(user));
  const client = makeTestQueryClient();
  client.setQueryData(AUTH_ME_KEY, user);
  return client;
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
  /** The history state the first entry carries, as a `navigate` with `state` leaves it. */
  state?: unknown;
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
  { route = '/', state, client }: RenderRoutesOptions = {},
): RenderResult & { client: QueryClient; router: TestRouter } {
  const queryClient = client ?? makeTestQueryClient();
  const router = createMemoryRouter(routes, {
    initialEntries: [state === undefined ? route : { pathname: route, state }],
  });

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

/**
 * Serve the page under `prefix`, as a Django shell does with `data-url-prefix`.
 *
 * `@/portal/urlPrefix` reads the attribute once, when it is first imported, so the
 * module cache is dropped as well: a module the test imports dynamically afterwards
 * reads `prefix`, while the ones imported at the top of the file keep the empty one.
 * Pair it with `clearUrlPrefix` in an `afterEach`.
 */
export function stampUrlPrefix(prefix: string): void {
  document.documentElement.dataset.urlPrefix = prefix;
  vi.resetModules();
}

/** Take `data-url-prefix` off `<html>` again and drop the module cache. */
export function clearUrlPrefix(): void {
  delete document.documentElement.dataset.urlPrefix;
  vi.resetModules();
}
