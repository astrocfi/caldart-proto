/** The member check and the aircraft check: open to every role that verifies. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const leaderRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['dart_leader', 'account_admin', 'user_admin', 'verifier']} />,
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
