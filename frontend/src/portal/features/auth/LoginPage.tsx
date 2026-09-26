import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { useAuth, useLogin, useReactivate } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { isGuidePath, openGuide } from '@/portal/guide';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { maskEmail } from '@/portal/masks';
import { EMAIL_MESSAGE, isEmailAddress } from '@/portal/masks';
import { AuthShell } from './AuthShell';
import { FormAlert, fieldError } from './form';

/** The `code` a sign-in refusal carries when the account is deactivated. */
const DEACTIVATED_CODE = 'deactivated';

/** True when `error` is the refusal of a deactivated account whose password matched. */
function isDeactivated(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.status !== 403) return false;
  const body = error.body as Record<string, unknown> | null;
  return body?.code === DEACTIVATED_CODE;
}

/** Only same-site paths are followed, so `?next=` cannot bounce off-site. */
export function safeNext(raw: string | null): string {
  if (!raw) return '/';
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/';
  return raw;
}

/**
 * `/login` — email + password, honoring `?next=`, with the address prefilled from
 * `?email=` when it is given.
 *
 * A deactivated account whose password matched is offered reactivation: the same
 * credentials go to `POST /auth/reactivate`, which signs the person in.
 *
 * `next` is a portal route, except when it names a page of the user guide:
 * Django sends a signed-out reader here with the guide page as `next`, and the
 * guide lives outside the SPA, so that one is a full-page navigation.
 */
export function LoginPage(): JSX.Element {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const login = useLogin();
  const reactivate = useReactivate();
  const { isAuthenticated, isLoading } = useAuth();
  // `?email=` prefills the address, for a link from somewhere that already knows it.
  const [email, setEmail] = useState(() => params.get('email') ?? '');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);

  const next = safeNext(params.get('next'));
  const isGuide = isGuidePath(next);
  const isSignedIn = !isLoading && isAuthenticated;

  useEffect(() => {
    if (isSignedIn && isGuide) openGuide(next);
  }, [isSignedIn, isGuide, next]);

  if (isSignedIn) return isGuide ? <></> : <Navigate to={next} replace />;

  const handleSignedIn = () => {
    if (isGuide) {
      openGuide(next);
      return;
    }
    void navigate(next, { replace: true });
  };

  return (
    <AuthShell
      title="Sign in"
      lede="Use the email address CalDART has on file."
      footer={
        <>
          Not a member yet? <Link to="/join">Join CalDART</Link>.
        </>
      }
    >
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (!isEmailAddress(email)) {
            setEmailError(EMAIL_MESSAGE);
            return;
          }
          setEmailError(null);
          reactivate.reset();
          login.mutate({ email, password }, { onSuccess: handleSignedIn });
        }}
      >
        <Field
          label="Email address"
          required
          error={emailError ?? fieldError(login.error, 'email')}
        >
          {(props) => (
            <MaskedInput
              {...props}
              type="email"
              name="email"
              autoComplete="username"
              required
              mask={maskEmail}
              value={email}
              onValueChange={(next) => setEmail(next)}
            />
          )}
        </Field>
        <Field label="Password" required error={fieldError(login.error, 'password')}>
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

        <FormAlert error={login.error} handled={['email', 'password', 'code']} />

        <div className="auth__actions">
          <Button type="submit" disabled={login.isPending}>
            {login.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
          <Link to="/forgot-password">Forgot your password?</Link>
        </div>
      </form>

      {isDeactivated(login.error) ? (
        <Card title="Reactivate my account">
          <p>{login.error.message}</p>
          <p>Reactivating brings back your roles and any membership that has not yet run out.</p>
          <FormAlert error={reactivate.error} />
          <Button
            disabled={reactivate.isPending}
            onClick={() => reactivate.mutate({ email, password }, { onSuccess: handleSignedIn })}
          >
            {reactivate.isPending ? 'Reactivating…' : 'Reactivate my account'}
          </Button>
        </Card>
      ) : null}
    </AuthShell>
  );
}
