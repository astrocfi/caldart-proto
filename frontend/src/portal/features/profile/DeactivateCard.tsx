/**
 * The **Deactivate my account** card at the foot of `/profile`.
 *
 * The member confirms with their current password.  The server cancels any automatic
 * renewal or recurring donation, suspends the membership, and ends the session; the
 * card then goes to the sign-in page, where the account can be reactivated any time.
 */
import { useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import type { MembershipStatus } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { useDeactivate } from './api';

const DEACTIVATED_TOAST = 'Your account is deactivated. Sign in any time to reactivate it.';

/** What deactivating does to a current membership, or null when there is none. */
function membershipNotice(membership: MembershipStatus): string | null {
  if (membership.status !== 'current') return null;
  if (membership.expires_on === null) {
    return 'Your lifetime membership is current. Deactivating ends it now; if you reactivate, it resumes.';
  }
  return (
    `Your membership is current through ${formatDate(membership.expires_on)}. ` +
    'Deactivating ends it now; if you reactivate before that date, it resumes.'
  );
}

/** Deactivates the signed-in member's own account once they give their password. */
export function DeactivateCard(): JSX.Element {
  const { user } = useAuth();
  const deactivate = useDeactivate();
  const navigate = useNavigate();
  const toast = useToast();
  const [password, setPassword] = useState('');

  const notice = user ? membershipNotice(user.membership) : null;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    deactivate.mutate(
      { current_password: password },
      {
        onSuccess: () => {
          toast.show(DEACTIVATED_TOAST, 'success');
          void navigate('/login', { replace: true });
        },
      },
    );
  };

  return (
    <Card title="Deactivate my account">
      <p>
        You will be signed out and will not appear in any list. Your information and your payment
        history are kept. Sign in again any time to reactivate.
      </p>
      {notice ? <p>{notice}</p> : null}
      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="Current password"
          required
          error={fieldError(deactivate.error, 'current_password')}
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
        <FormAlert error={deactivate.error} handled={['current_password']} />
        <Button type="submit" variant="danger" disabled={password === '' || deactivate.isPending}>
          Deactivate my account
        </Button>
      </form>
    </Card>
  );
}
