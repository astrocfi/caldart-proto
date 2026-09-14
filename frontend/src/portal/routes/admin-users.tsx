/** User and role administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminUsersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['user_admin']} />,
    children: [
      {
        path: 'admin/users',
        lazy: async () => ({
          Component: (await import('../features/admin-users/UsersListPage')).UsersListPage,
        }),
      },
      {
        path: 'admin/users/:id',
        lazy: async () => ({
          Component: (await import('../features/admin-users/UserDetailPage')).UserDetailPage,
        }),
      },
    ],
  },
];
