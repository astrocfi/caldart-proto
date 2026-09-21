import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { usePasswordResetConfirm } from '../../auth/useAuth';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Field } from '../../components/Field';
import { Page } from '../../components/Page';
import { FormAlert, fieldError } from './form';

/** `/reset-password?uid=&token=` — the form the reset email links to. */
export function ResetPasswordPage(): JSX.Element {
  const [params] = useSearchParams();
  const confirm = usePasswordResetConfirm();
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [mismatch, setMismatch] = useState<string | null>(null);

  const uid = params.get('uid') ?? '';
  const token = params.get('token') ?? '';

  if (!uid || !token) {
    return (
      <Page title="Reset your password" eyebrow="Password reset">
        <EmptyState
          title="That link is incomplete"
          description="Open the link from the reset email exactly as it arrived, or ask for a new one."
          action={<Link to="/forgot-password">Request a new link</Link>}
        />
      </Page>
    );
  }

  if (confirm.isSuccess) {
    return (
      <Page title="Password changed" eyebrow="Password reset">
        <Card className="auth-card">
          <p>Your new password is saved. Sign in with it to get back to the portal.</p>
        </Card>
        <p>
          <Link to="/login">Go to sign in</Link>
        </p>
      </Page>
    );
  }

  return (
    <Page
      title="Choose a new password"
      eyebrow="Password reset"
      lede="Pick something you do not use anywhere else."
    >
      <Card className="auth-card">
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (password !== repeat) {
              setMismatch('The two passwords do not match.');
              return;
            }
            setMismatch(null);
            confirm.mutate({ uid, token, new_password: password });
          }}
        >
          <Field
            label="New password"
            required
            error={fieldError(confirm.error, 'new_password')}
            hint="At least 8 characters, and not a password you have used elsewhere."
          >
            {(props) => (
              <input
                {...props}
                type="password"
                name="new_password"
                autoComplete="new-password"
                autoFocus
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </Field>
          <Field label="Repeat new password" required error={mismatch}>
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

          <FormAlert error={confirm.error} handled={['new_password']} />

          <div className="cluster">
            <Button type="submit" disabled={confirm.isPending}>
              {confirm.isPending ? 'Saving…' : 'Save new password'}
            </Button>
            <Link to="/forgot-password">Request a new link</Link>
          </div>
        </form>
      </Card>
    </Page>
  );
}
