/**
 * The Profile tab of a member record: the same fields as "New member", plus
 * the account's active switch and the administrator-only notes.
 */
import { useState } from 'react';

import { Button, Card, useToast } from '../../components';
import { ProfileFieldsets } from '../profile/ProfileFieldsets';
import { EMPTY_PROFILE_FORM, formToPatch, profileToForm } from '../profile/form';
import {
  AccountFields,
  AdminOnlyFields,
  adminOnlyDraft,
  adminProfilePayload,
} from './MemberFormFields';
import type { AccountDraft } from './MemberFormFields';
import { useDarts, useUpdateMember } from './api';
import { splitErrors } from './errors';
import type { MemberDetail } from '../../api/types';

function accountDraftFrom(member: MemberDetail): AccountDraft {
  return {
    email: member.email,
    first_name: member.first_name,
    last_name: member.last_name,
    password: '',
    is_active: member.is_active,
  };
}

export function MemberProfileTab({ member }: { member: MemberDetail }) {
  const toast = useToast();
  const darts = useDarts();
  const update = useUpdateMember(member.id);

  const [account, setAccount] = useState(() => accountDraftFrom(member));
  const [profile, setProfile] = useState(() =>
    member.profile ? profileToForm(member.profile) : EMPTY_PROFILE_FORM,
  );
  const [adminOnly, setAdminOnly] = useState(() => adminOnlyDraft(member.profile));

  const errors = splitErrors(update.error);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    update.mutate(
      {
        email: account.email.trim(),
        first_name: account.first_name,
        last_name: account.last_name,
        is_active: account.is_active,
        profile: adminProfilePayload(formToPatch(profile), adminOnly),
      },
      { onSuccess: () => toast.show('Member saved.', 'success') },
    );
  };

  return (
    <Card>
      <form onSubmit={submit} noValidate>
        {errors.detail ? (
          <p role="alert" className="field__error">
            {errors.detail}
          </p>
        ) : null}

        <AccountFields value={account} onChange={setAccount} errors={errors.account} withActive />
        <ProfileFieldsets
          value={profile}
          onChange={setProfile}
          errors={errors.profile}
          darts={darts.data ?? []}
          dartsLoading={darts.isPending}
        />
        <AdminOnlyFields value={adminOnly} onChange={setAdminOnly} errors={errors.profile} />

        <div className="cluster">
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? 'Saving…' : 'Save changes'}
          </Button>
          {member.profile?.aircraft.length ? (
            <p className="muted">
              Aircraft on file: {member.profile.aircraft.map((one) => one.n_number).join(', ')}
            </p>
          ) : null}
        </div>
      </form>
    </Card>
  );
}
