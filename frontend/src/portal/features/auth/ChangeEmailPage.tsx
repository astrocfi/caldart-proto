import { useState } from 'react';
import type { JSX } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { pendingEmailNotice } from '@/portal/auth/pendingEmail';
import { useAuth, useEmailChange } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { ResendVerificationButton } from '@/portal/components/ResendVerificationButton';
import { useToast } from '@/portal/components/Toast';
import { FormAlert, fieldError } from './form';
import { safeNext } from './LoginPage';

/**
 * `/change-email` — ask to move your own account to another address while signed in.
 *
 * Nothing changes until the link the server mails to the new address is followed: the
 * account keeps signing in with the address it has, and the page says so while the
 * change waits, with a control that sends the link again.  After asking, the member
 * goes back to the portal page named by `?next=`, or to the dashboard.
 */
export function ChangeEmailPage(): JSX.Element {
  const change = useEmailChange();
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const next = safeNext(params.get('next'));
  const pending = user ? pendingEmailNotice(user) : null;

  return (
    <Page
      title="Change email"
      lede={
        user
          ? `Your sign-in address is ${user.email}. We will send a link to the new address; the change takes effect when you open it.`
          : undefined
      }
    >
      {pending !== null ? (
        <Card title="Change waiting">
          <p role="status">{pending}</p>
          <div className="cluster card__footer">
            <ResendVerificationButton />
          </div>
        </Card>
      ) : null}
      <Card>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            change.mutate(
              { email, current_password: password },
              {
                onSuccess: (changed) => {
                  toast.show(
                    pendingEmailNotice(changed) ?? 'Your email address is unchanged.',
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

          <div className="cluster card__footer">
            <Button type="submit" disabled={change.isPending}>
              {change.isPending ? 'Saving…' : 'Change email'}
            </Button>
          </div>
        </form>
      </Card>
    </Page>
  );
}
