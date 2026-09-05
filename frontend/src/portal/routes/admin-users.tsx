/** User and role administration routes (PLAN §8).  Owned by `feat/auth-portal`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/auth-portal';

export const adminUsersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['user_admin']} />,
    children: [
      { path: 'admin/users', element: comingSoon('Users and roles', BRANCH) },
      { path: 'admin/users/:id', element: comingSoon('User record', BRANCH) },
    ],
  },
];
