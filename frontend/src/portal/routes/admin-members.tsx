/** Member administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { MemberCreatePage, MemberDetailPage, MembersListPage } from '../features/admin-members';

export const adminMembersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      { path: 'admin/members', element: <MembersListPage /> },
      { path: 'admin/members/new', element: <MemberCreatePage /> },
      { path: 'admin/members/:id', element: <MemberDetailPage /> },
    ],
  },
];
