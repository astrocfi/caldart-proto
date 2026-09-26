import { useEffect, useRef } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { User } from '@/portal/api/types';
import { useAuth, useEmailVerify } from '@/portal/auth/useAuth';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Page } from '@/portal/components/Page';

/** What the server says about every unusable link, shown too for a link with no token. */
const INVALID_LINK = 'That verification link is invalid or has expired.';

/**
 * `/verify-email?token=…` — the page a verification message links to.
 *
 * It posts the token as soon as it loads, signed in or not, since the mail client
 * may open the link in a browser that has no session.  Continuing goes on with the
 * join wizard when the visitor still has a profile to fill in, to the dashboard
 * when they are signed in otherwise, and to the sign-in page when they are not.
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
      <Page title="Verifying your email address" eyebrow="Your account">
        <p className="muted" role="status">
          Checking the link…
        </p>
      </Page>
    );
  }

  return (
    <Page title="Email verified" eyebrow="Your account">
      <Card className="auth-card">
        <p>{verify.data.email} is verified.</p>
        <div className="cluster card__footer">
          <ButtonLink to={continueTo(user)}>Continue</ButtonLink>
        </div>
      </Card>
    </Page>
  );
}

/** Where `Continue` goes: the join wizard, the dashboard, or the sign-in page. */
function continueTo(user: User | null): string {
  if (user === null) return '/login?next=/';
  return user.profile_complete ? '/' : '/join';
}

/** The server's reason for refusing the link, or the one message for a missing token. */
function failureMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return INVALID_LINK;
  return error.fieldErrors.token ?? error.message;
}

function VerifyFailed({ message }: { message: string }): JSX.Element {
  return (
    <Page title="Email not verified" eyebrow="Your account">
      <Card className="auth-card">
        <p className="field__error" role="alert">
          {message}
        </p>
        <p>
          <Link to="/login">Sign in</Link> and use Resend verification message on your dashboard to
          get a new one.
        </p>
      </Card>
    </Page>
  );
}
