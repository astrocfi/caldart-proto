/** Member home (PLAN §8).  Owned by `feat/profile-join`. */
import type { RouteObject } from 'react-router-dom';

import { comingSoon } from './placeholder';

const BRANCH = 'feat/profile-join';

export const dashboardRoutes: RouteObject[] = [
  { index: true, element: comingSoon('Member dashboard', BRANCH) },
];
