/**
 * Auth routes (PLAN §8).  Owned by `feat/auth-portal`.
 *
 * `/login` is a real, working form so the shell is usable from the start; the
 * rest are placeholders until that branch lands.
 */
import { useState } from 'react';
import type { RouteObject } from 'react-router-dom';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useAuth, useLogin, useLogout } from '../auth/useAuth';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { Field } from '../components/Field';
import { Page } from '../components/Page';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/auth-portal';

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const login = useLogin();
  const { isAuthenticated, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const next = params.get('next') ?? '/';

  if (!isLoading && isAuthenticated) return <Navigate to={next} replace />;

  const error = login.error instanceof ApiError ? login.error : null;

  return (
    <Page
      title="Sign in"
      eyebrow="CalDART members"
      lede="Use the email address CalDART has on file."
    >
      <Card className="auth-card">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            login.mutate(
              { email, password },
              { onSuccess: () => navigate(next, { replace: true }) },
            );
          }}
        >
          <Field label="Email address" required error={error?.fieldErrors.email ?? null}>
            {(props) => (
              <input
                {...props}
                type="email"
                name="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            )}
          </Field>
          <Field label="Password" required error={error?.fieldErrors.password ?? null}>
            {(props) => (
              <input
                {...props}
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>
          {error && Object.keys(error.fieldErrors).length === 0 ? (
            <p className="field__error" role="alert">
              {error.message}
            </p>
          ) : null}
          <div className="cluster">
            <Button type="submit" disabled={login.isPending}>
              {login.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
            <a href="/portal/forgot-password">Forgot your password?</a>
          </div>
        </form>
      </Card>
    </Page>
  );
}

export function LogoutPage() {
  const logout = useLogout();
  const { isAuthenticated, isLoading } = useAuth();

  if (!isLoading && isAuthenticated && logout.isIdle) logout.mutate();
  if (!isLoading && !isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Page title="Signing out" eyebrow="CalDART">
      <Card>
        <p className="muted">One moment…</p>
      </Card>
    </Page>
  );
}

export const authRoutes: RouteObject[] = [
  { path: 'login', element: <LoginPage /> },
  { path: 'logout', element: <LogoutPage /> },
  { path: 'forgot-password', element: comingSoon('Forgot password', BRANCH) },
  { path: 'reset-password', element: comingSoon('Reset password', BRANCH) },
  { path: 'change-password', element: comingSoon('Change password', BRANCH) },
];
