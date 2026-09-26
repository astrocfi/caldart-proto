/**
 * The portal's route table.
 *
 * Every feature owns one file in this directory exporting a `RouteObject[]`;
 * this module only concatenates them.
 *
 * `/login` and friends sit outside `RequireAuth`; everything else is behind it,
 * inside the portal layout.
 *
 * Most feature routes name their page with `lazy`, so its code arrives only
 * when somebody opens it; the root route's hydrate fallback covers that wait on
 * the first page a visitor asks for, and a later move between screens holds the
 * current one until the next page's chunk arrives.  The sign-in, dashboard, and
 * not-found screens stay eager: they are where a visitor lands, and an extra
 * request there would only delay them.
 */
import type { RouteObject } from 'react-router-dom';

import { RequireAuth } from '../auth/guards';
import { Loading } from '../components/Loading';
import { PortalLayout } from '../layout/PortalLayout';
import { NotFound } from './not-found';
import { adminAircraftRoutes } from './admin-aircraft';
import { adminDartsRoutes } from './admin-darts';
import { adminMembersRoutes } from './admin-members';
import { adminPaymentsRoutes } from './admin-payments';
import { adminRemindersRoutes } from './admin-reminders';
import { adminReportsRoutes } from './admin-reports';
import { adminUsersRoutes } from './admin-users';
import { authRoutes } from './auth';
import { dashboardRoutes } from './dashboard';
import { donateRoutes } from './donate';
import { joinRoutes, renewRoutes } from './join';
import { leaderRoutes } from './leader';
import { paymentsRoutes } from './payments';
import { profileRoutes } from './profile';
import { systemRoutes } from './system';

/** Routes reachable without signing in. */
export const publicRoutes: RouteObject[] = [...authRoutes, ...joinRoutes];

/** Routes that require a session. */
export const privateRoutes: RouteObject[] = [
  ...dashboardRoutes,
  ...renewRoutes,
  ...profileRoutes,
  ...paymentsRoutes,
  ...donateRoutes,
  ...leaderRoutes,
  ...adminMembersRoutes,
  ...adminAircraftRoutes,
  ...adminDartsRoutes,
  ...adminPaymentsRoutes,
  ...adminRemindersRoutes,
  ...adminReportsRoutes,
  ...adminUsersRoutes,
  ...systemRoutes,
];

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <PortalLayout />,
    hydrateFallbackElement: <Loading />,
    children: [
      ...publicRoutes,
      { element: <RequireAuth />, children: privateRoutes },
      { path: '*', element: <NotFound /> },
    ],
  },
];
