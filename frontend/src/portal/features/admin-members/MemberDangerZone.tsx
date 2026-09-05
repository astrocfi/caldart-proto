/**
 * The Danger zone tab: hard-delete a member record (PLAN §6.4).
 *
 * Deleting takes the profile, membership terms and payment history with it, so
 * the button stays disabled until the administrator has typed the member's
 * email address back.  The server refuses to delete you, or a system
 * administrator unless you are one, and says so here.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Card, Field, useToast } from '../../components';
import { useDeleteMember } from './api';
import { splitErrors } from './errors';
import type { MemberDetail } from './types';

export function MemberDangerZone({ member }: { member: MemberDetail }) {
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

  return (
    <Card title="Delete this member" eyebrow="Danger zone">
      <p>
        Deleting <strong>{member.name}</strong> also deletes their profile,{' '}
        {member.memberships.length} membership term
        {member.memberships.length === 1 ? '' : 's'} and {member.payments.length} payment
        {member.payments.length === 1 ? '' : 's'}. This cannot be undone.
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
