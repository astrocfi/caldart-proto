/** DART leader routes (PLAN §8).  Owned by `feat/aircraft-leader`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/aircraft-leader';

export const leaderRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['dart_leader']} />,
    children: [
      { path: 'leader', element: comingSoon('Member check', BRANCH) },
      { path: 'leader/aircraft', element: comingSoon('Aircraft check', BRANCH) },
    ],
  },
];
