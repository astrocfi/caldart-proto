/**
 * Auth routes.
 *
 * These sit in `publicRoutes`, outside the shell's `RequireAuth`, so
 * `/change-password` and `/change-email` carry their own guard.  `/verify-email`
 * is public: a verification link may be opened in a browser with no session.
 * `/change-email` stays open to a reader who has not finished joining, so a
 * mistyped address can be corrected from the verify step; `/change-password` does
 * not.
 */
import type { RouteObject } from 'react-router-dom';

import { RequireAuth, RequireOnboarded } from '../auth/guards';
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  LoginPage,
  ResetPasswordPage,
} from '../features/auth';
import { ChangeEmailPage } from '../features/auth/ChangeEmailPage';
import { VerifyEmailPage } from '../features/auth/VerifyEmailPage';

export const authRoutes: RouteObject[] = [
  { path: 'login', element: <LoginPage /> },
  { path: 'forgot-password', element: <ForgotPasswordPage /> },
  { path: 'reset-password', element: <ResetPasswordPage /> },
  { path: 'verify-email', element: <VerifyEmailPage /> },
  {
    path: 'change-password',
    element: (
      <RequireAuth>
        <RequireOnboarded>
          <ChangePasswordPage />
        </RequireOnboarded>
      </RequireAuth>
    ),
  },
  {
    path: 'change-email',
    element: (
      <RequireAuth>
        <ChangeEmailPage />
      </RequireAuth>
    ),
  },
];
