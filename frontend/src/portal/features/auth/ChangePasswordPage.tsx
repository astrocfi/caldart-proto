/** `/change-password` — change your own password while signed in. */
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { usePasswordChange } from '../../auth/useAuth';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Field } from '../../components/Field';
import { Page } from '../../components/Page';
import { useToast } from '../../components/Toast';
import { FormAlert, fieldError } from './form';

export function ChangePasswordPage() {
  const change = usePasswordChange();
  const toast = useToast();
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [mismatch, setMismatch] = useState<string | null>(null);

  return (
    <Page
      title="Change your password"
      eyebrow="Your account"
      lede="You stay signed in on this device."
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
            change.mutate(
              { current_password: current, new_password: password },
              {
                onSuccess: () => {
                  toast.show('Your password has been changed.', 'success');
                  setCurrent('');
                  setPassword('');
                  setRepeat('');
                },
              },
            );
          }}
        >
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
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
              />
            )}
          </Field>
          <Field
            label="New password"
            required
            error={fieldError(change.error, 'new_password')}
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

          <FormAlert error={change.error} handled={['current_password', 'new_password']} />

          <div className="cluster">
            <Button type="submit" disabled={change.isPending}>
              {change.isPending ? 'Saving…' : 'Change password'}
            </Button>
            <Link to="/">Back to the dashboard</Link>
          </div>
        </form>
      </Card>
    </Page>
  );
}
