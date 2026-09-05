/** Join and renew routes (PLAN §8).  Owned by `feat/profile-join`. */
import type { RouteObject } from 'react-router-dom';

import { comingSoon } from './placeholder';

const BRANCH = 'feat/profile-join';

/** Joining is open to visitors who do not have an account yet. */
export const joinRoutes: RouteObject[] = [
  { path: 'join', element: comingSoon('Join CalDART', BRANCH) },
  { path: 'join/:step', element: comingSoon('Join CalDART', BRANCH) },
];

/** Renewing needs a session, so it is mounted behind `RequireAuth`. */
export const renewRoutes: RouteObject[] = [
  { path: 'renew', element: comingSoon('Renew your membership', BRANCH) },
];
