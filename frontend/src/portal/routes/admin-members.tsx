/** Member administration routes (PLAN §8).  Owned by `feat/members-admin`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/members-admin';

export const adminMembersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      { path: 'admin/members', element: comingSoon('Members administration', BRANCH) },
      { path: 'admin/members/new', element: comingSoon('Add a member', BRANCH) },
      { path: 'admin/members/:id', element: comingSoon('Member record', BRANCH) },
    ],
  },
];
