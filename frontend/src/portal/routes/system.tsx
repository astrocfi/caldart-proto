/** System administration routes (PLAN §8).  Owned by `feat/ops`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/ops';

export const systemRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['system_admin']} />,
    children: [{ path: 'system', element: comingSoon('Health, backups and reminders', BRANCH) }],
  },
];
