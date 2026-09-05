/** Aircraft administration routes (PLAN §8).  Owned by `feat/aircraft-leader`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/aircraft-leader';

export const adminAircraftRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      { path: 'admin/aircraft', element: comingSoon('Aircraft register', BRANCH) },
      { path: 'admin/aircraft/:id', element: comingSoon('Aircraft record', BRANCH) },
    ],
  },
];
