/** Join and renew routes (PLAN §8).  Owned by `feat/profile-join`. */
import type { RouteObject } from 'react-router-dom';

import { JoinWizard } from '../features/join/JoinWizard';
import { RenewPage } from '../features/join/RenewPage';

/** Joining is open to visitors who do not have an account yet. */
export const joinRoutes: RouteObject[] = [
  { path: 'join', element: <JoinWizard /> },
  { path: 'join/:step', element: <JoinWizard /> },
];

/** Renewing needs a session, so it is mounted behind `RequireAuth`. */
export const renewRoutes: RouteObject[] = [{ path: 'renew', element: <RenewPage /> }];
