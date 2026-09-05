/** User and role administration routes (PLAN §8).  Owned by `feat/auth-portal`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { UserDetailPage, UsersListPage } from '../features/admin-users';

export const adminUsersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['user_admin']} />,
    children: [
      { path: 'admin/users', element: <UsersListPage /> },
      { path: 'admin/users/:id', element: <UserDetailPage /> },
    ],
  },
];
