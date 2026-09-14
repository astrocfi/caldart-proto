/** DART leader routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { LeaderAircraftPage } from '../features/leader/LeaderAircraftPage';
import { LeaderSearchPage } from '../features/leader/LeaderSearchPage';

export const leaderRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['dart_leader', 'account_admin']} />,
    children: [
      { path: 'leader', element: <LeaderSearchPage /> },
      { path: 'leader/aircraft', element: <LeaderAircraftPage /> },
    ],
  },
];
