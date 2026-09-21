/**
 * Route guards.
 *
 * Both guards wait for `GET /auth/me` to settle, so a slow answer never
 * flashes the sign-in page at somebody who is in fact signed in, and then
 * take one of three outcomes: an anonymous visitor goes to `/login?next=`;
 * a signed-in user who lacks the role gets the 403 page; and a check that
 * failed outright gets an error with a "Try again" button, because a server
 * error is not a sign-out.
 */
import type { JSX, ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { Location } from 'react-router-dom';

import type { RoleSlug } from '../api/types';
import { Button, ButtonLink } from '../components/Button';
import { EmptyState } from '../components/EmptyState';
import { Loading } from '../components/Loading';
import { Page } from '../components/Page';
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
function AuthUnavailable({ onRetry, isRetrying }: AuthUnavailableProps): ReactNode {
  return (
    <Page title="Sign-in check failed" eyebrow="Error">
      <div role="alert">
        <EmptyState
          title="We could not check your sign-in"
          description="The server did not answer. You are probably still signed in, so try again in a moment."
          action={
            <Button onClick={onRetry} disabled={isRetrying}>
              Try again
            </Button>
          }
        />
      </div>
    </Page>
  );
}

/** Route guard: renders the outlet only once `GET /auth/me` confirms a signed-in user. */
export function RequireAuth({ children }: { children?: ReactNode }): JSX.Element {
  const { isAuthenticated, isLoading, isRefetching, error, refetch } = useAuth();
  const location = useLocation();

  if (isLoading) return <Loading />;
  // A failed check with nothing cached: React Query keeps `data` across a
  // failed refetch, so a signed-in member keeps their page instead.
  if (!isAuthenticated && error != null)
    return <AuthUnavailable onRetry={refetch} isRetrying={isRefetching} />;
  if (!isAuthenticated) return <Navigate to={loginRedirect(location)} replace />;
  return <>{children ?? <Outlet />}</>;
}

export interface RequireRoleProps {
  roles: RoleSlug[];
  children?: ReactNode;
}

/** Route guard: renders the outlet only for a signed-in user who holds one of `roles`. */
export function RequireRole({ roles, children }: RequireRoleProps): JSX.Element {
  const { isAuthenticated, isLoading, isRefetching, error, refetch, roles: userRoles } = useAuth();
  const location = useLocation();

  if (isLoading) return <Loading />;
  if (!isAuthenticated && error != null)
    return <AuthUnavailable onRetry={refetch} isRetrying={isRefetching} />;
  if (!isAuthenticated) return <Navigate to={loginRedirect(location)} replace />;
  if (!hasAnyRole(userRoles, roles)) return <Forbidden roles={roles} />;
  return <>{children ?? <Outlet />}</>;
}

/** Human wording for the role a page wanted, e.g. "user admin". */
function roleLabel(slug: RoleSlug): string {
  return slug.replace(/_/g, ' ');
}

/** The 403 page shown when a signed-in user lacks the role a route needs. */
export function Forbidden({ roles = [] }: { roles?: RoleSlug[] }): JSX.Element {
  const needed = roles.map(roleLabel).join(' or ');
  return (
    <Page title="Not allowed" eyebrow="403">
      <EmptyState
        title="You do not have access to this page"
        description={
          needed
            ? `It is open to the ${needed} role. Ask a CalDART administrator if you should have it — your other pages are in the menu.`
            : 'Ask a CalDART administrator if you think you should. Your other pages are in the menu.'
        }
        action={<ButtonLink to="/">Go to the dashboard</ButtonLink>}
      />
    </Page>
  );
}
