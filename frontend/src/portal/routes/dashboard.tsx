/** Member home. */
import type { RouteObject } from 'react-router-dom';

import { DashboardPage } from '../features/dashboard/DashboardPage';

export const dashboardRoutes: RouteObject[] = [{ index: true, element: <DashboardPage /> }];
