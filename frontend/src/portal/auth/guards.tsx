/**
 * Route guards.
 *
 * `RequireAuth` sends anonymous visitors to `/login?next=`; `RequireRole`
 * renders a 403 page when the user is signed in but lacks the role.  Both wait
 * for `GET /auth/me` to settle first, so a slow answer never flashes the
 * sign-in page at somebody who is in fact signed in.
 */
import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import type { Location } from 'react-router-dom';

import type { RoleSlug } from '../api/types';
import { ButtonLink } from '../components/Button';
import { EmptyState } from '../components/EmptyState';
import { Page } from '../components/Page';
import { hasAnyRole } from '../nav';
import { useAuth } from './useAuth';

/** `/login?next=<where they were heading>`. */
export function loginRedirect(location: Pick<Location, 'pathname' | 'search'>): string {
  return `/login?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`;
}

function Loading(): ReactNode {
  return (
    <div className="portal-loading" role="status" aria-live="polite">
      <span className="visually-hidden">Loading</span>
    </div>
  );
}

export function RequireAuth({ children }: { children?: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <Loading />;
  if (!isAuthenticated) return <Navigate to={loginRedirect(location)} replace />;
  return <>{children ?? <Outlet />}</>;
}

export interface RequireRoleProps {
  roles: RoleSlug[];
  children?: ReactNode;
}

export function RequireRole({ roles, children }: RequireRoleProps) {
  const { isAuthenticated, isLoading, roles: userRoles } = useAuth();
  const location = useLocation();

  if (isLoading) return <Loading />;
  if (!isAuthenticated) return <Navigate to={loginRedirect(location)} replace />;
  if (!hasAnyRole(userRoles, roles)) return <Forbidden roles={roles} />;
  return <>{children ?? <Outlet />}</>;
}

/** Human wording for the role a page wanted, e.g. "user admin". */
function roleLabel(slug: RoleSlug): string {
  return slug.replace(/_/g, ' ');
}

export function Forbidden({ roles = [] }: { roles?: RoleSlug[] }) {
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
