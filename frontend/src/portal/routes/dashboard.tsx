/** Member home (PLAN §8).  Owned by `feat/profile-join`. */
import type { RouteObject } from 'react-router-dom';

import { DashboardPage } from '../features/dashboard/DashboardPage';

export const dashboardRoutes: RouteObject[] = [{ index: true, element: <DashboardPage /> }];
