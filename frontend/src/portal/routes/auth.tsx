/**
 * Auth routes.
 *
 * These sit in `publicRoutes`, outside the shell's `RequireAuth`, so
 * `/change-password` carries its own guard.
 */
import type { RouteObject } from 'react-router-dom';

import { RequireAuth } from '../auth/guards';
import {
  ChangePasswordPage,
  ForgotPasswordPage,
  LoginPage,
  ResetPasswordPage,
} from '../features/auth';

export const authRoutes: RouteObject[] = [
  { path: 'login', element: <LoginPage /> },
  { path: 'forgot-password', element: <ForgotPasswordPage /> },
  { path: 'reset-password', element: <ResetPasswordPage /> },
  {
    path: 'change-password',
    element: (
      <RequireAuth>
        <ChangePasswordPage />
      </RequireAuth>
    ),
  },
];
