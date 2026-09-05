/** Profile routes (PLAN §8).  Owned by `feat/profile-join`. */
import type { RouteObject } from 'react-router-dom';

import { comingSoon } from './placeholder';

const BRANCH = 'feat/profile-join';

export const profileRoutes: RouteObject[] = [
  { path: 'profile', element: comingSoon('My profile', BRANCH) },
  { path: 'profile/aircraft', element: comingSoon('My aircraft', BRANCH) },
];
