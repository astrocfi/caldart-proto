/** DART leader routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const leaderRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['dart_leader', 'account_admin']} />,
    children: [
      {
        path: 'leader',
        lazy: async () => ({
          Component: (await import('../features/leader/LeaderSearchPage')).LeaderSearchPage,
        }),
      },
      {
        path: 'leader/aircraft',
        lazy: async () => ({
          Component: (await import('../features/leader/LeaderAircraftPage')).LeaderAircraftPage,
        }),
      },
    ],
  },
];
