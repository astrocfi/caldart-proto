/**
 * The portal application shell (PLAN §8): TanStack Query, the toast queue and
 * the router mounted under the `/portal` basename.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';

import { ApiError } from './api/client';
import { ToastProvider } from './components/Toast';
import { routes } from './routes';

export const PORTAL_BASENAME = '/portal';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Re-requesting a 4xx will not help.
          if (error instanceof ApiError && error.status < 500) return false;
          return failureCount < 2;
        },
      },
      mutations: { retry: false },
    },
  });
}

const router = createBrowserRouter(routes, { basename: PORTAL_BASENAME });

export interface AppProvidersProps {
  client?: QueryClient;
  children: ReactNode;
}

/** Providers only — tests wrap their own router around this. */
export function AppProviders({ client, children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={client ?? createQueryClient()}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

export function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
