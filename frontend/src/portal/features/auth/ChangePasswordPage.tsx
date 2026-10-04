import { useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { usePasswordChange } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { useToast } from '@/portal/components/Toast';
import { AuthShell } from './AuthShell';
import { FormAlert, fieldError } from './form';

/** `/change-password` — change your own password while signed in. */
export function ChangePasswordPage(): JSX.Element {
  const change = usePasswordChange();
  const toast = useToast();
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [mismatch, setMismatch] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, change.error);
  // The server's complaint about a box goes once the box is edited.
  const serverErrors = useFreshErrors(
    change.error,
    { current_password: current, new_password: password },
    {
      current_password: fieldError(change.error, 'current_password'),
      new_password: fieldError(change.error, 'new_password'),
    },
  );

  return (
    <AuthShell title="Change your password" lede="You stay signed in on this device.">
      <form
        ref={formRef}
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (password !== repeat) {
            // What the server said about the last attempt no longer applies.
            change.reset();
            setMismatch('The two passwords do not match.');
            refusal.refuse();
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
        <Field label="Current password" required error={serverErrors.current_password}>
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
          error={serverErrors.new_password}
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
              onChange={(event) => {
                setPassword(event.target.value);
                setMismatch(null);
              }}
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
              onChange={(event) => {
                setRepeat(event.target.value);
                setMismatch(null);
              }}
            />
          )}
        </Field>

        <FormAlert error={change.error} handled={['current_password', 'new_password']} />

        <div className="auth__actions">
          <Button type="submit" disabled={change.isPending}>
            {change.isPending ? 'Saving…' : 'Change password'}
          </Button>
          <Link to="/">Back to the dashboard</Link>
          <RefusedSubmitNote count={refusal.count} />
        </div>
      </form>
    </AuthShell>
  );
}
