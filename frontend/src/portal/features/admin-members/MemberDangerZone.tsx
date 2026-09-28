/**
 * The Danger zone tab: hard-delete a member record.
 *
 * Deleting takes the profile and the membership terms with it, so the button
 * stays disabled until the administrator has typed the member's email address
 * back.  A payment is a financial record and is kept whatever happens to the
 * account: the server hands a member's payments to a "Deleted member {id}"
 * account, and the tab says so before the delete.  The server refuses to delete
 * you, or a system administrator unless you are one, and says so here.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { Card } from '@/portal/components/Card';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { useDeleteMember } from './api';
import { splitErrors } from './errors';
import type { MemberDetail } from '@/portal/api/types';

function PaymentsNote({ member }: { member: MemberDetail }) {
  const count = member.payments.length;
  if (count === 0) return null;
  const records =
    count === 1 ? '1 payment record. It stays' : `${count} payment records. They stay`;
  return (
    <p>
      {member.name} has {records} in the books under the name Deleted member {member.id}.
    </p>
  );
}

/** The Danger zone tab: hard-delete a member record, keeping their payments in the books. */
export function MemberDangerZone({ member }: { member: MemberDetail }): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const remove = useDeleteMember(member.id);
  const [confirmation, setConfirmation] = useState('');

  const confirmed = confirmation.trim().toLowerCase() === member.email.toLowerCase();
  const errors = splitErrors(remove.error);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!confirmed) return;
    remove.mutate(undefined, {
      onSuccess: () => {
        toast.show(`${member.name} has been deleted.`, 'success');
        void navigate('/admin/members');
      },
    });
  };

  return (
    <Card title="Delete this member" eyebrow="Danger zone">
      <p>
        Deleting <strong>{member.name}</strong> also deletes their profile and{' '}
        {member.memberships.length} membership term
        {member.memberships.length === 1 ? '' : 's'}. This cannot be undone.
      </p>
      <PaymentsNote member={member} />
      <form onSubmit={handleSubmit} noValidate>
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
        <DeleteButton
          label="Delete member"
          type="submit"
          variant="danger"
          small={false}
          disabled={!confirmed || remove.isPending}
        >
          {remove.isPending ? 'Deleting…' : 'Delete member'}
        </DeleteButton>
      </form>
    </Card>
  );
}
