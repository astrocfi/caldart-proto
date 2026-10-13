import { useCallback, useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { LoginResult } from '@/portal/api/types';
import { isMfaChallenge, useAuth, useLogin, useReactivate } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { openGuide } from '@/portal/guide';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { RefusedSubmitNote, useRefusedSubmit } from '@/portal/components/RefusedSubmit';
import { addressProblem, maskEmail } from '@/portal/masks';
import { PORTAL_BASENAME, sitePath } from '@/portal/urlPrefix';
import { CodeStep, EnrollStep } from '@/portal/features/two-factor/SignInSteps';
import { AuthShell } from './AuthShell';
import { FormAlert, fieldError } from './form';

/** What the sign-in screen says under its title: what the portal is, and which address. */
const LEDE =
  'The member portal is where CalDART members and friends keep their details, pay, and ' +
  'renew. Sign in with the email address CalDART has on file.';

/** What the password box says when it is left empty. */
const PASSWORD_MESSAGE = 'Enter your password.';

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
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return '/';
  return raw;
}

/** Where the Wagtail admin and the Django admin live, outside the portal. */
const ADMIN_PREFIXES = [sitePath('/admin/'), sitePath('/django-admin/')];

/** True when `path` starts with `prefix`, a directory ending in a slash, or is it. */
function isUnder(path: string, prefix: string): boolean {
  return (
    path === prefix.slice(0, -1) ||
    path.startsWith(prefix) ||
    path.startsWith(`${prefix.slice(0, -1)}?`)
  );
}

/** True when `path` is a page of the Wagtail or Django admin. */
export function isAdminPath(path: string): boolean {
  return ADMIN_PREFIXES.some((prefix) => isUnder(path, prefix));
}

/**
 * Where `?next=` leads: a route of the portal, or a page Django serves outside it.
 *
 * Everything that sends a reader here names a full site path: the portal's own guard
 * and links name a portal route under `PORTAL_BASENAME`, which is stripped to the
 * route; Django names a page of the user guide, of an admin site, or of the public
 * site.  So a path under the portal's base is a portal route and any other is a page of
 * the site.  No `next`, or an unsafe one, is the dashboard.
 */
export type NextTarget = { kind: 'portal'; path: string } | { kind: 'site'; path: string };

/** The target `raw` names, after `safeNext`. */
export function nextTarget(raw: string | null): NextTarget {
  const next = safeNext(raw);
  if (raw === null || next !== raw) return { kind: 'portal', path: '/' };
  if (isUnder(next, `${PORTAL_BASENAME}/`)) {
    return { kind: 'portal', path: next.slice(PORTAL_BASENAME.length) || '/' };
  }
  return { kind: 'site', path: next };
}

/** Which step of signing in is on screen. */
type Step = 'password' | 'verify' | 'enroll';

/**
 * `/login` — email + password, honoring `?next=`, with the address prefilled from
 * `?email=` when it is given.
 *
 * An account that needs a second factor is then asked for a code from its
 * authenticator app or a backup code, or, when it must use one and has none, is taken
 * through setting one up and saving its backup codes; only then is it signed in.
 *
 * A deactivated account whose password matched is offered reactivation: the same
 * credentials go to `POST /auth/reactivate`, which signs the person in the same way.
 *
 * `next` is a portal route, or a page of the site -- the user guide, an admin site, or a
 * members-only page -- that Django sent a signed-out reader here from (`nextTarget`);
 * going to one of those is a full-page navigation.  Somebody already signed in who arrives with an admin page as
 * `next` is taken to the dashboard instead, since the admin site sent them here because
 * their account cannot open it.
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
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  // A refusal, the form's own or the server's, takes the focus to what is wrong and
  // says so beside the button.
  const refusal = useRefusedSubmit(formRef, login.error);

  const [step, setStep] = useState<Step>('password');
  const [expired, setExpired] = useState<string | null>(null);

  const target = nextTarget(params.get('next'));
  const next = target.path;
  const isSite = target.kind === 'site';
  const isSignedIn = !isLoading && isAuthenticated;

  // Somebody already signed in goes on to a page of the site, except an admin page: the
  // admin sent them here because their account cannot open it.
  const isOpenSitePage = isSite && !isAdminPath(next);
  useEffect(() => {
    if (isSignedIn && isOpenSitePage && step === 'password') openGuide(next);
  }, [isSignedIn, isOpenSitePage, next, step]);

  const handleExpired = useCallback((message: string) => {
    setExpired(message);
    setPassword('');
    setStep('password');
  }, []);

  if (isSignedIn && step === 'password') {
    if (isSite && !isAdminPath(next)) return <></>;
    return <Navigate to={isSite ? '/' : next} replace />;
  }

  const handleSignedIn = () => {
    if (isSite) {
      // A full-page navigation, as the guide's own pages are opened.
      openGuide(next);
      return;
    }
    void navigate(next, { replace: true });
  };

  const handleResult = (result: LoginResult) => {
    if (!isMfaChallenge(result)) {
      handleSignedIn();
      return;
    }
    setExpired(null);
    setStep(result.mfa);
  };

  const handleStartAgain = () => {
    setPassword('');
    setStep('password');
  };

  if (step === 'verify') {
    return (
      <CodeStep onSignedIn={handleSignedIn} onExpired={handleExpired} onCancel={handleStartAgain} />
    );
  }
  if (step === 'enroll') {
    return (
      <EnrollStep
        onSignedIn={handleSignedIn}
        onExpired={handleExpired}
        onCancel={handleStartAgain}
      />
    );
  }

  return (
    <AuthShell
      title="Sign in"
      lede={LEDE}
      footer={
        <>
          Not a member yet? <Link to="/join">Join CalDART</Link>.
        </>
      }
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          // Both boxes are checked at once, so an empty form names both of them.
          const badEmail = addressProblem(email);
          const badPassword = password === '' ? PASSWORD_MESSAGE : null;
          setEmailError(badEmail);
          setPasswordError(badPassword);
          if (badEmail !== null || badPassword !== null) {
            refusal.refuse();
            return;
          }
          reactivate.reset();
          setExpired(null);
          login.mutate({ email, password }, { onSuccess: handleResult });
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
        <Field
          label="Password"
          required
          error={passwordError ?? fieldError(login.error, 'password')}
        >
          {(props) => (
            <input
              {...props}
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setPasswordError(null);
              }}
            />
          )}
        </Field>

        {expired !== null && login.error === null ? (
          <p className="field__error" role="alert">
            {expired}
          </p>
        ) : null}
        <FormAlert error={login.error} handled={['email', 'password', 'code']} />

        <div className="auth__actions">
          <Button type="submit" disabled={login.isPending}>
            {login.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
          <RefusedSubmitNote count={refusal.count} />
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
            onClick={() => reactivate.mutate({ email, password }, { onSuccess: handleResult })}
          >
            {reactivate.isPending ? 'Reactivating…' : 'Reactivate my account'}
          </Button>
        </Card>
      ) : null}
    </AuthShell>
  );
}
