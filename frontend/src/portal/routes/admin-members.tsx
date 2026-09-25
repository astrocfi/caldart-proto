/** Member administration routes: a DART leader reads the list, the rest is the account administrator's. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminMembersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin', 'dart_leader']} />,
    children: [
      {
        path: 'admin/members',
        lazy: async () => ({
          Component: (await import('../features/admin-members/MembersListPage')).MembersListPage,
        }),
      },
    ],
  },
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      {
        path: 'admin/members/new',
        lazy: async () => ({
          Component: (await import('../features/admin-members/MemberCreatePage')).MemberCreatePage,
        }),
      },
      {
        path: 'admin/members/:id',
        lazy: async () => ({
          Component: (await import('../features/admin-members/MemberDetailPage')).MemberDetailPage,
        }),
      },
    ],
  },
];
