import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { User } from '@/portal/api/types';
import { useAuth, useEmailVerify } from '@/portal/auth/useAuth';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { isOnboarded } from '@/portal/features/join/steps';
import { PORTAL_BASENAME } from '@/portal/urlPrefix';
import { AuthShell } from './AuthShell';
import { FormAlert, fieldError } from './form';

/** What the server says about every unusable link, shown too for a link missing its token. */
const INVALID_LINK = 'That verification link is invalid or has expired.';

/** The `code` the server answers with when the link opens an account and needs a password. */
const PASSWORD_REQUIRED_CODE = 'password_required';

/**
 * `/verify-email?token=…` — the page a verification message links to.
 *
 * The same link completes a change of address when it was mailed to the new address;
 * the answer's `changed` says so, and the page then names the new sign-in address.
 *
 * It posts the token as soon as it loads, signed in or not, since the mail client
 * may open the link in a browser without a session.  A link that opens a donor's
 * account is answered with a request for a password, so the page then asks the person
 * who followed it to choose one and posts again.  Continuing goes on with the join
 * wizard when the visitor has not finished joining (a profile to fill in, or a
 * membership to pay for), to the dashboard when they have, and to the sign-in page,
 * then the join wizard, when nobody is signed in.
 */
export function VerifyEmailPage(): JSX.Element {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const verify = useEmailVerify();
  const { user } = useAuth();
  const posted = useRef(false);
  const [needsPassword, setNeedsPassword] = useState(false);

  useEffect(() => {
    // A second post is harmless server-side, but one request is enough, and
    // React runs this effect twice in development.
    if (token === '' || posted.current) return;
    posted.current = true;
    verify.mutate(
      { token },
      {
        onError: (error) => {
          if (isPasswordRequired(error)) setNeedsPassword(true);
        },
      },
    );
  }, [token, verify]);

  if (token === '') return <VerifyFailed message={INVALID_LINK} />;

  if (verify.isSuccess) {
    return (
      <AuthShell title={verify.data.changed ? 'Email address changed' : 'Email verified'}>
        <p>
          {verify.data.changed
            ? `${verify.data.email} is your sign-in address from now on.`
            : `${verify.data.email} is verified.`}
        </p>
        <div className="auth__actions">
          <ButtonLink to={continueTo(user, verify.data.email)}>Continue</ButtonLink>
        </div>
      </AuthShell>
    );
  }

  if (needsPassword) {
    return (
      <ChoosePasswordForm
        error={isPasswordRequired(verify.error) ? null : verify.error}
        isPending={verify.isPending}
        onSubmit={(password) => verify.mutate({ token, password })}
      />
    );
  }

  if (verify.isError) return <VerifyFailed message={failureMessage(verify.error)} />;

  return (
    <AuthShell title="Verifying your email address">
      <p className="muted" role="status">
        Checking the link…
      </p>
    </AuthShell>
  );
}

/**
 * Where `Continue` goes: the join wizard, the dashboard, or the sign-in page with the
 * verified address filled in.  Signing in from there goes on to the join wizard, which
 * resumes wherever the account stands, so a donor who registered, and so didn't have a
 * session until now, goes on to the profile step.
 */
function continueTo(user: User | null, email: string): string {
  if (user === null) {
    const next = encodeURIComponent(`${PORTAL_BASENAME}/join`);
    return `/login?next=${next}&email=${encodeURIComponent(email)}`;
  }
  return isOnboarded(user) ? '/' : '/join';
}

/** True when `error` is the server asking for the password a donor's link needs. */
function isPasswordRequired(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 400) return false;
  const body = error.body as Record<string, unknown> | null;
  return body?.code === PASSWORD_REQUIRED_CODE;
}

/** The server's reason for refusing the link, or the one message for a missing token. */
function failureMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return INVALID_LINK;
  return error.fieldErrors.token ?? error.message;
}

interface ChoosePasswordFormProps {
  /** The refusal of the last password posted, or `null` before one is. */
  error: Error | null;
  isPending: boolean;
  onSubmit: (password: string) => void;
}

/** The password a donor's account will sign in with, asked of whoever followed the link. */
function ChoosePasswordForm({ error, isPending, onSubmit }: ChoosePasswordFormProps): JSX.Element {
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [mismatch, setMismatch] = useState<string | null>(null);

  return (
    <AuthShell
      title="Choose your password"
      lede="This opens your portal account. Pick something you do not use anywhere else."
    >
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (password !== repeat) {
            setMismatch('The two passwords do not match.');
            return;
          }
          setMismatch(null);
          onSubmit(password);
        }}
      >
        <Field
          label="Password"
          required
          error={fieldError(error, 'password')}
          hint="At least 8 characters. Avoid common passwords such as password1."
        >
          {(props) => (
            <input
              {...props}
              type="password"
              name="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
        </Field>
        <Field label="Repeat password" required error={mismatch}>
          {(props) => (
            <input
              {...props}
              type="password"
              name="repeat_password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
            />
          )}
        </Field>

        <FormAlert error={error} handled={['password', 'code']} />

        <div className="auth__actions">
          <Button type="submit" disabled={isPending}>
            {isPending ? 'Saving…' : 'Open my account'}
          </Button>
        </div>
      </form>
    </AuthShell>
  );
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
