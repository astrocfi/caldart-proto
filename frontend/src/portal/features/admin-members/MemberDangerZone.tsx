/**
 * The Danger zone tab: hard-delete a member record.
 *
 * A payment is a financial record and is kept whatever happens to the account,
 * so a member who has ever paid cannot be deleted at all: the tab explains that
 * and points at deactivation instead of offering a form the server would refuse.
 *
 * For a member who never paid, deleting takes the profile and the membership
 * terms with it, so the button stays disabled until the administrator has typed
 * the member's email address back.  The server refuses to delete you, or a
 * system administrator unless you are one, and says so here.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Card, Field, useToast } from '../../components';
import { useDeleteMember } from './api';
import { splitErrors } from './errors';
import type { MemberDetail } from '../../api/types';

function PaymentsKept({ member }: { member: MemberDetail }) {
  const count = member.payments.length;
  return (
    <Card title="This member cannot be deleted" eyebrow="Danger zone">
      <p>
        {member.name} has {count} payment record{count === 1 ? '' : 's'}, which must be kept.
        Deleting the account would take the payment history with it, so the delete is refused.
      </p>
      <p>
        Clear Account is active on the Profile tab instead. A deactivated member cannot sign in, and
        their profile, membership terms and payments stay exactly as they are.
      </p>
    </Card>
  );
}

/** The Danger zone tab: hard-delete a member record, once payments allow it. */
export function MemberDangerZone({ member }: { member: MemberDetail }): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const remove = useDeleteMember(member.id);
  const [confirmation, setConfirmation] = useState('');

  const confirmed = confirmation.trim().toLowerCase() === member.email.toLowerCase();
  const errors = splitErrors(remove.error);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!confirmed) return;
    remove.mutate(undefined, {
      onSuccess: () => {
        toast.show(`${member.name} has been deleted.`, 'success');
        navigate('/admin/members');
      },
    });
  };

  if (member.payments.length > 0) return <PaymentsKept member={member} />;

  return (
    <Card title="Delete this member" eyebrow="Danger zone">
      <p>
        Deleting <strong>{member.name}</strong> also deletes their profile and{' '}
        {member.memberships.length} membership term
        {member.memberships.length === 1 ? '' : 's'}. This cannot be undone.
      </p>
      <form onSubmit={submit} noValidate>
        {errors.detail ? (
          <p role="alert" className="field__error">
            {errors.detail}
          </p>
        ) : null}
        <Field
          label={`Type ${member.email} to confirm`}
          hint="The delete button stays disabled until the address matches."
        >
          {(props) => (
            <input
              {...props}
              type="text"
              autoComplete="off"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          )}
        </Field>
        <Button type="submit" variant="danger" disabled={!confirmed || remove.isPending}>
          {remove.isPending ? 'Deleting…' : 'Delete member'}
        </Button>
      </form>
    </Card>
  );
}
