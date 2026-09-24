import { useState } from 'react';
import type { JSX } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';

import { useAuth, useLogin } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { maskEmail } from '@/portal/masks';
import { EMAIL_MESSAGE, isEmailAddress } from '@/portal/masks';
import { Page } from '@/portal/components/Page';
import { FormAlert, fieldError } from './form';

/** Only same-site paths are followed, so `?next=` cannot bounce off-site. */
export function safeNext(raw: string | null): string {
  if (!raw) return '/';
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/';
  return raw;
}

/** `/login` — email + password, honoring `?next=`. */
export function LoginPage(): JSX.Element {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const login = useLogin();
  const { isAuthenticated, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);

  const next = safeNext(params.get('next'));

  if (!isLoading && isAuthenticated) return <Navigate to={next} replace />;

  return (
    <Page
      title="Sign in"
      eyebrow="CalDART members"
      lede="Use the email address CalDART has on file."
    >
      <Card className="auth-card">
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (!isEmailAddress(email)) {
              setEmailError(EMAIL_MESSAGE);
              return;
            }
            setEmailError(null);
            login.mutate(
              { email, password },
              {
                onSuccess: () => {
                  void navigate(next, { replace: true });
                },
              },
            );
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

          <FormAlert error={login.error} handled={['email', 'password']} />

          <div className="cluster">
            <Button type="submit" disabled={login.isPending}>
              {login.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
            <Link to="/forgot-password">Forgot your password?</Link>
          </div>
        </form>
      </Card>

      <p className="muted">
        Not a member yet? <Link to="/join">Join CalDART</Link>.
      </p>
    </Page>
  );
}
