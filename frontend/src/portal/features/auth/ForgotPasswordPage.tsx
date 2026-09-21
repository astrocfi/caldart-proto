import { useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { usePasswordResetRequest } from '../../auth/useAuth';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Field } from '../../components/Field';
import { Page } from '../../components/Page';
import { FormAlert, fieldError } from './form';

/** `/forgot-password` — ask for a reset link. */
export function ForgotPasswordPage(): JSX.Element {
  const request = usePasswordResetRequest();
  const [email, setEmail] = useState('');

  // The API answers 204 whether or not the address is registered, so the page
  // must say the same thing either way.
  if (request.isSuccess) {
    return (
      <Page title="Check your email" eyebrow="Password reset">
        <Card className="auth-card">
          <p>
            If an account uses <strong>{request.variables?.email}</strong>, a reset link is on its
            way. The link can be used once and expires in a few days.
          </p>
          <p className="muted">
            Nothing arrived? Check the spam folder, then{' '}
            <Link to="/forgot-password" onClick={() => request.reset()}>
              try another address
            </Link>
            .
          </p>
        </Card>
        <p className="muted">
          <Link to="/login">Back to sign in</Link>
        </p>
      </Page>
    );
  }

  return (
    <Page
      title="Forgot your password?"
      eyebrow="CalDART members"
      lede="Tell us the address on your account and we will email you a link to set a new password."
    >
      <Card className="auth-card">
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            request.mutate({ email });
          }}
        >
          <Field label="Email address" required error={fieldError(request.error, 'email')}>
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

          <FormAlert error={request.error} handled={['email']} />

          <div className="cluster">
            <Button type="submit" disabled={request.isPending}>
              {request.isPending ? 'Sending…' : 'Email me a link'}
            </Button>
            <Link to="/login">Back to sign in</Link>
          </div>
        </form>
      </Card>
    </Page>
  );
}
