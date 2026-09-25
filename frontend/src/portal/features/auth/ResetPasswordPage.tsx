import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { usePasswordResetConfirm } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { AuthShell } from './AuthShell';
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
      <AuthShell title="Reset your password">
        <p>
          <strong>That link is incomplete.</strong> Open the link from the reset email exactly as it
          arrived, or ask for a new one.
        </p>
        <div className="auth__actions">
          <Link to="/forgot-password">Request a new link</Link>
        </div>
      </AuthShell>
    );
  }

  if (confirm.isSuccess) {
    return (
      <AuthShell title="Password changed">
        <p>Your new password is saved. Sign in with it to get back to the portal.</p>
        <div className="auth__actions">
          <Link to="/login">Go to sign in</Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password" lede="Pick something you do not use anywhere else.">
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

        <div className="auth__actions">
          <Button type="submit" disabled={confirm.isPending}>
            {confirm.isPending ? 'Saving…' : 'Save new password'}
          </Button>
          <Link to="/forgot-password">Request a new link</Link>
        </div>
      </form>
    </AuthShell>
  );
}
