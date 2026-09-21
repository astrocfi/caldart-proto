/** Join and renew routes. */
import type { ComponentType } from 'react';
import type { RouteObject } from 'react-router-dom';

async function joinWizard(): Promise<{ Component: ComponentType }> {
  return { Component: (await import('../features/join/JoinWizard')).JoinWizard };
}

/** Joining is open to visitors who do not have an account yet. */
export const joinRoutes: RouteObject[] = [
  { path: 'join', lazy: joinWizard },
  { path: 'join/:step', lazy: joinWizard },
];

/** Renewing needs a session, so it is mounted behind `RequireAuth`. */
export const renewRoutes: RouteObject[] = [
  {
    path: 'renew',
    lazy: async () => ({ Component: (await import('../features/join/RenewPage')).RenewPage }),
  },
];
