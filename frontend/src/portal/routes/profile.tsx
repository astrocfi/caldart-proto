/** Profile routes. */
import type { RouteObject } from 'react-router-dom';

import { MyAircraftPage } from '../features/profile/MyAircraftPage';
import { ProfilePage } from '../features/profile/ProfilePage';

export const profileRoutes: RouteObject[] = [
  { path: 'profile', element: <ProfilePage /> },
  { path: 'profile/aircraft', element: <MyAircraftPage /> },
];
