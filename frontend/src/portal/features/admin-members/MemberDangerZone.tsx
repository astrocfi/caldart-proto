/**
 * The Danger zone tab: the account actions (make a friend, deactivate, reactivate),
 * then hard-deleting the member record.
 *
 * Deleting takes the profile and the membership terms with it, so the button
 * stays disabled until the administrator has typed the member's email address
 * back.  A payment is a financial record and is kept whatever happens to the
 * account: the server hands a member's payments to a "Deleted member {id}"
 * account, and the tab says so before the delete.  The server refuses to delete
 * you, or a system administrator unless you are one, and says so here.  A deleted
 * donor's reader lands back on the donors report, where the gifts show under the
 * tombstone's name; everybody else on the member list.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '@/portal/auth/useAuth';
import { Card } from '@/portal/components/Card';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Field } from '@/portal/components/Field';
import { useToast } from '@/portal/components/Toast';
import { MemberAccountActions } from './MemberAccountActions';
import { useDeleteMember } from './api';
import { splitErrors } from './errors';
import { recordHome } from './recordHome';
import { TOMBSTONE_NOTE } from './tombstone';
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

/**
 * The Danger zone tab: the account actions, then the delete, which keeps the member's
 * payments in the books. A "Deleted member N" record offers neither, only the reason.
 */
export function MemberDangerZone({ member }: { member: MemberDetail }): JSX.Element {
  if (member.is_tombstone) {
    return (
      <Card title="Kept for the books" eyebrow="Danger zone">
        <p>{TOMBSTONE_NOTE}</p>
      </Card>
    );
  }
  return <DeleteZone member={member} />;
}

/** The account actions and the delete form, for any record but a tombstone's. */
function DeleteZone({ member }: { member: MemberDetail }): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const remove = useDeleteMember(member.id);
  const { roles } = useAuth();
  const [confirmation, setConfirmation] = useState('');

  const confirmed = confirmation.trim().toLowerCase() === member.email.toLowerCase();
  const errors = splitErrors(remove.error);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!confirmed) return;
    remove.mutate(undefined, {
      onSuccess: () => {
        toast.show(`${member.name} has been deleted.`, 'success');
        void navigate(recordHome(member, roles).to);
      },
    });
  };

  return (
    <>
      <MemberAccountActions member={member} />
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
    </>
  );
}
