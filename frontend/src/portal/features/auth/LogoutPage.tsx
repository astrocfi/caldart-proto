/** `/logout` — end the session, empty the cache, land on the sign-in page. */
import { useEffect } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth, useLogout } from '../../auth/useAuth';
import { Card } from '../../components/Card';
import { Page } from '../../components/Page';

export function LogoutPage() {
  const logout = useLogout();
  const { isAuthenticated, isLoading } = useAuth();
  const { mutate, isIdle } = logout;

  useEffect(() => {
    // One shot: `isIdle` goes false as soon as the request is in flight, and
    // `useLogout` empties the query cache on the way out.
    if (!isLoading && isAuthenticated && isIdle) mutate();
  }, [isLoading, isAuthenticated, isIdle, mutate]);

  if (!isLoading && !isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Page title="Signing out" eyebrow="CalDART">
      <Card>
        <p className="muted" role="status">
          One moment…
        </p>
      </Card>
    </Page>
  );
}
