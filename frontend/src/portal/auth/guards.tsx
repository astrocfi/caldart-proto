/**
 * Route guards.
 *
 * `RequireAuth` and `RequireRole` wait for `GET /auth/me` to settle, so a slow answer never
 * flashes the sign-in page at somebody who is in fact signed in, and then
 * take one of three outcomes: an anonymous visitor goes to `/login?next=`;
 * a signed-in user who lacks the role gets the 403 page; and a check that
 * failed outright gets an error with a "Try again" button, because a server
 * error is not a sign-out.  `RequireOnboarded` sits inside `RequireAuth` and holds a
 * signed-in reader who has not finished joining at the join wizard's step they still
 * owe.
 */
import type { JSX, ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { Location } from 'react-router-dom';

import type { RoleSlug } from '../api/types';
import { roleLabel } from '../choices';
import { Button, ButtonLink } from '../components/Button';
import { Loading } from '../components/Loading';
import { Page } from '../components/Page';
import { furthestJoinStep, isOnboarded } from '../features/join/steps';
import { hasAnyRole } from '../nav';
import { useAuth } from './useAuth';

/** `/login?next=<where they were heading>`. */
export function loginRedirect(location: Pick<Location, 'pathname' | 'search'>): string {
  return `/login?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`;
}

interface AuthUnavailableProps {
  onRetry: () => void;
  isRetrying: boolean;
}

/**
 * Shown when `GET /auth/me` failed and nothing is cached, so the portal has no
 * idea who this is.  Sending them to the sign-in page would claim a sign-out
 * that never happened, and hide the outage behind it.
 */
function AuthUnavailable({ onRetry: handleRetry, isRetrying }: AuthUnavailableProps): ReactNode {
  return (
    <Page title="Sign-in check failed" noEyebrow>
      <div role="alert" className="stack">
        <p>
          We could not check your sign-in: the server did not answer. You are probably still signed
          in, so try again in a moment.
        </p>
        <div className="cluster">
          <Button onClick={handleRetry} disabled={isRetrying}>
            Try again
          </Button>
        </div>
      </div>
    </Page>
  );
}

/** Route guard: renders the outlet only once `GET /auth/me` confirms a signed-in user. */
export function RequireAuth({ children }: { children?: ReactNode }): JSX.Element {
  const { isAuthenticated, isLoading, isRefetching, error, refetch: handleRetry } = useAuth();
  const location = useLocation();

  if (isLoading) return <Loading />;
  // A failed check with nothing cached: React Query keeps `data` across a
  // failed refetch, so a signed-in member keeps their page instead.
  if (!isAuthenticated && error != null)
    return <AuthUnavailable onRetry={handleRetry} isRetrying={isRefetching} />;
  if (!isAuthenticated) return <Navigate to={loginRedirect(location)} replace />;
  return <>{children ?? <Outlet />}</>;
}

/**
 * Route guard: renders the outlet only for a reader who has finished joining.
 *
 * A signed-in reader whose address is unverified, whose profile is incomplete, or who
 * chose membership and has not yet paid is sent to that step of the join wizard
 * (`/join/verify`, `/join/profile`, or `/join/pay`), which is also where they left
 * it, since a step is left only by finishing it.  While `/auth/me` is being
 * refetched, such a reader sees the loading state instead, since the answer may
 * already say they have finished (a payment that has just settled, say).  Nobody
 * signed in, or a check still in flight, is left to `RequireAuth`, which this guard
 * sits inside.
 */
export function RequireOnboarded({ children }: { children?: ReactNode }): JSX.Element {
  const { user, isRefetching } = useAuth();
  if (user !== null && !isOnboarded(user)) {
    // A payment or a verification refetches `/auth/me`; until it answers, the cached
    // reader is the one from before it, so wait rather than send them back a step.
    if (isRefetching) return <Loading />;
    return <Navigate to={`/join/${furthestJoinStep(user)}`} replace />;
  }
  return <>{children ?? <Outlet />}</>;
}

export interface RequireRoleProps {
  roles: RoleSlug[];
  children?: ReactNode;
}

/** Route guard: renders the outlet only for a signed-in user who holds one of `roles`. */
export function RequireRole({ roles, children }: RequireRoleProps): JSX.Element {
  const {
    isAuthenticated,
    isLoading,
    isRefetching,
    error,
    refetch: handleRetry,
    roles: userRoles,
  } = useAuth();
  const location = useLocation();

  if (isLoading) return <Loading />;
  if (!isAuthenticated && error != null)
    return <AuthUnavailable onRetry={handleRetry} isRetrying={isRefetching} />;
  if (!isAuthenticated) return <Navigate to={loginRedirect(location)} replace />;
  if (!hasAnyRole(userRoles, roles)) return <Forbidden roles={roles} />;
  return <>{children ?? <Outlet />}</>;
}

/** The 403 page shown when a signed-in user lacks the role a route needs. */
export function Forbidden({ roles = [] }: { roles?: RoleSlug[] }): JSX.Element {
  const needed = roles.map(roleLabel).join(' or ');
  return (
    <Page
      title="Not allowed"
      noEyebrow
      lede={
        needed
          ? `You do not have access to this page. It is open to the ${needed} role. Ask a CalDART administrator if you should have it — your other pages are in the menu.`
          : 'You do not have access to this page. Ask a CalDART administrator if you think you should. Your other pages are in the menu.'
      }
    >
      <div className="cluster">
        <ButtonLink to="/">Go to the dashboard</ButtonLink>
      </div>
    </Page>
  );
}
