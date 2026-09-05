/**
 * Route guards (PLAN §8).
 *
 * `RequireAuth` sends anonymous visitors to `/login?next=`; `RequireRole`
 * renders a 403 page when the user is signed in but lacks the role.
 */
import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import type { RoleSlug } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { Page } from '../components/Page';
import { hasAnyRole } from '../nav';
import { useAuth } from './useAuth';

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
  if (!isAuthenticated) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
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
  if (!isAuthenticated) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (!hasAnyRole(userRoles, roles)) return <Forbidden />;
  return <>{children ?? <Outlet />}</>;
}

export function Forbidden() {
  return (
    <Page title="Not allowed" eyebrow="403">
      <EmptyState
        title="You do not have access to this page"
        description="Ask a CalDART administrator if you think you should. Your other pages are in the menu."
      />
    </Page>
  );
}
