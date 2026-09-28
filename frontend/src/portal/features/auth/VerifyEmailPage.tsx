import { useEffect, useRef } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { User } from '@/portal/api/types';
import { useAuth, useEmailVerify } from '@/portal/auth/useAuth';
import { ButtonLink } from '@/portal/components/Button';
import { isOnboarded } from '@/portal/features/join/steps';
import { AuthShell } from './AuthShell';

/** What the server says about every unusable link, shown too for a link with no token. */
const INVALID_LINK = 'That verification link is invalid or has expired.';

/**
 * `/verify-email?token=…` — the page a verification message links to.
 *
 * It posts the token as soon as it loads, signed in or not, since the mail client
 * may open the link in a browser that has no session.  Continuing goes on with the
 * join wizard when the visitor has not finished joining (a profile to fill in, or a
 * membership to pay for), to the dashboard when they have, and to the sign-in page,
 * then the join wizard, when nobody is signed in.
 */
export function VerifyEmailPage(): JSX.Element {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const verify = useEmailVerify();
  const { user } = useAuth();
  const posted = useRef(false);

  useEffect(() => {
    // The token is spent server-side on nothing, but one request is enough, and
    // React runs this effect twice in development.
    if (token === '' || posted.current) return;
    posted.current = true;
    verify.mutate(token);
  }, [token, verify]);

  if (token === '' || verify.isError) {
    return <VerifyFailed message={failureMessage(verify.error)} />;
  }

  if (!verify.isSuccess) {
    return (
      <AuthShell title="Verifying your email address">
        <p className="muted" role="status">
          Checking the link…
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Email verified">
      <p>{verify.data.email} is verified.</p>
      <div className="auth__actions">
        <ButtonLink to={continueTo(user, verify.data.email)}>Continue</ButtonLink>
      </div>
    </AuthShell>
  );
}

/**
 * Where `Continue` goes: the join wizard, the dashboard, or the sign-in page with the
 * verified address filled in.  Signing in from there goes on to the join wizard, which
 * resumes wherever the account stands, so a donor who registered, and so had no
 * session until now, goes on to the profile step.
 */
function continueTo(user: User | null, email: string): string {
  if (user === null) return `/login?next=/join&email=${encodeURIComponent(email)}`;
  return isOnboarded(user) ? '/' : '/join';
}

/** The server's reason for refusing the link, or the one message for a missing token. */
function failureMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return INVALID_LINK;
  return error.fieldErrors.token ?? error.message;
}

function VerifyFailed({ message }: { message: string }): JSX.Element {
  return (
    <AuthShell title="Email not verified">
      <p className="field__error" role="alert">
        {message}
      </p>
      <p>
        <Link to="/login">Sign in</Link> and press Resend verification message on the screen you
        land on to get a new one.
      </p>
    </AuthShell>
  );
}
