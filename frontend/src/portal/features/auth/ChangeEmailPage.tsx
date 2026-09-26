import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { useEmailChange } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { FormAlert, fieldError } from './form';
import { safeNext } from './LoginPage';

/**
 * `/change-email` — move your own account to another address while signed in.
 *
 * The new address is unverified until its owner follows the link the server mails
 * to it.  Afterwards the member goes back to the portal page named by `?next=`, or
 * to the dashboard.
 */
export function ChangeEmailPage(): JSX.Element {
  const change = useEmailChange();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const next = safeNext(params.get('next'));

  return (
    <Page
      title="Change your email address"
      eyebrow="Your account"
      lede="You sign in with the new address, and we send it a verification message."
    >
      <Card className="auth-card">
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            change.mutate(
              { email, current_password: password },
              {
                onSuccess: (user) => {
                  toast.show(
                    `Your email is now ${user.email}. We sent a verification message to it.`,
                    'success',
                  );
                  void navigate(next, { replace: true });
                },
              },
            );
          }}
        >
          <Field label="New email address" required error={fieldError(change.error, 'email')}>
            {(props) => (
              <input
                {...props}
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            )}
          </Field>
          <Field
            label="Current password"
            required
            error={fieldError(change.error, 'current_password')}
          >
            {(props) => (
              <input
                {...props}
                type="password"
                name="current_password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>

          <FormAlert error={change.error} handled={['email', 'current_password']} />

          <div className="cluster">
            <Button type="submit" disabled={change.isPending}>
              {change.isPending ? 'Saving…' : 'Change email'}
            </Button>
            <Link to="/">Back to the dashboard</Link>
          </div>
        </form>
      </Card>
    </Page>
  );
}
