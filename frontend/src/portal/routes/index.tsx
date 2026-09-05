/**
 * The portal's route table (PLAN §8).
 *
 * Every feature owns one file in this directory exporting a `RouteObject[]`;
 * this module only concatenates them, so Phase 2 branches never collide here.
 *
 * `/login` and friends sit outside `RequireAuth`; everything else is behind it,
 * inside the portal layout.
 */
import type { RouteObject } from 'react-router-dom';

import { RequireAuth } from '../auth/guards';
import { PortalLayout } from '../layout/PortalLayout';
import { NotFound } from './not-found';
import { adminAircraftRoutes } from './admin-aircraft';
import { adminMembersRoutes } from './admin-members';
import { adminPaymentsRoutes } from './admin-payments';
import { adminUsersRoutes } from './admin-users';
import { authRoutes } from './auth';
import { dashboardRoutes } from './dashboard';
import { joinRoutes, renewRoutes } from './join';
import { leaderRoutes } from './leader';
import { profileRoutes } from './profile';
import { systemRoutes } from './system';

/** Routes reachable without signing in. */
export const publicRoutes: RouteObject[] = [...authRoutes, ...joinRoutes];

/** Routes that require a session. */
export const privateRoutes: RouteObject[] = [
  ...dashboardRoutes,
  ...renewRoutes,
  ...profileRoutes,
  ...leaderRoutes,
  ...adminMembersRoutes,
  ...adminAircraftRoutes,
  ...adminPaymentsRoutes,
  ...adminUsersRoutes,
  ...systemRoutes,
];

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <PortalLayout />,
    children: [
      ...publicRoutes,
      { element: <RequireAuth />, children: privateRoutes },
      { path: '*', element: <NotFound /> },
    ],
  },
];
