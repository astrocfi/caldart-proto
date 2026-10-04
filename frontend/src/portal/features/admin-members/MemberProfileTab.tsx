/**
 * The Profile tab of a member record: the same fields as "New member", plus the
 * administrator-only notes, under a Verification card for the pilot certificate, the
 * medical, and the photo ID, and an Aircraft card listing the airplanes on the profile.
 * **Verify** on the Verification card only checks items off: the details themselves are
 * corrected in the form. Deactivating the account is the Delete or deactivate tab's. A
 * "Deleted member N" record shows no form: the server refuses every edit to one.
 */
import { useRef, useState } from 'react';
import type { JSX } from 'react';

import { useDarts } from '@/portal/api/queries';
import type { MemberDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmailVerifiedText } from '@/portal/components/EmailVerifiedText';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { useToast } from '@/portal/components/Toast';
import { useFocusAfterSave } from '@/portal/components/focus';
import { ProfileFieldsets } from '@/portal/features/profile/ProfileFieldsets';
import { EMPTY_PROFILE_FORM, formToPatch, profileToForm } from '@/portal/features/profile/form';
import { MemberVerificationCard } from '@/portal/features/verification/MemberVerificationCard';
import {
  AccountFields,
  AdminOnlyFields,
  adminOnlyDraft,
  adminProfilePayload,
  kindPayload,
  missingNames,
  withoutEdited,
} from './MemberFormFields';
import type { AccountDraft, FieldErrors } from './MemberFormFields';
import { MemberAircraftCard } from './MemberAircraftCard';
import { useUpdateMember } from './api';
import { splitErrors } from './errors';
import { TOMBSTONE_NOTE } from './tombstone';

function accountDraftFrom(member: MemberDetail): AccountDraft {
  return {
    email: member.email,
    first_name: member.first_name,
    last_name: member.last_name,
    password: '',
    kind: member.kind,
  };
}

/** The Profile tab of a member record: profile fields plus the account controls. */
export function MemberProfileTab({ member }: { member: MemberDetail }): JSX.Element {
  const toast = useToast();
  const darts = useDarts();
  const update = useUpdateMember(member.id);

  const [account, setAccount] = useState(() => accountDraftFrom(member));
  const [profile, setProfile] = useState(() =>
    member.profile ? profileToForm(member.profile) : EMPTY_PROFILE_FORM,
  );
  const [adminOnly, setAdminOnly] = useState(() => adminOnlyDraft(member.profile));

  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, update.error);
  // The names left blank at the last save, until each is typed in again.
  const [nameErrors, setNameErrors] = useState<FieldErrors>({});
  useFocusAfterSave(formRef, update.isPending);
  const server = splitErrors(update.error);
  // A server error for a field goes once that field is edited.
  const errors = {
    ...server,
    account: { ...useFreshErrors(update.error, account, server.account), ...nameErrors },
    profile: useFreshErrors(update.error, { ...profile, ...adminOnly }, server.profile),
  };
  const verified = member.profile;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const missing = missingNames(account);
    setNameErrors(missing);
    if (Object.keys(missing).length > 0) {
      refusal.refuse();
      return;
    }
    update.mutate(
      {
        email: account.email.trim(),
        first_name: account.first_name,
        last_name: account.last_name,
        // An unchanged kind is left out: resending it would cancel a pending conversion.
        ...(account.kind === member.kind ? {} : kindPayload(account)),
        profile: adminProfilePayload(formToPatch(profile), adminOnly),
      },
      { onSuccess: () => toast.show('Member saved.', 'success') },
    );
  };

  return (
    <>
      {verified !== null ? (
        <MemberVerificationCard
          userId={member.id}
          profile={verified}
          checkable={member.is_active && member.kind !== 'donor'}
          checksOnly
        />
      ) : null}
      {verified !== null ? <MemberAircraftCard aircraft={verified.aircraft} /> : null}
      {member.is_tombstone ? (
        <Card>
          <p className="muted">{TOMBSTONE_NOTE}</p>
        </Card>
      ) : (
        <Card>
          <form ref={formRef} onSubmit={handleSubmit} noValidate>
            {errors.detail ? (
              <p role="alert" className="field__error">
                {errors.detail}
              </p>
            ) : null}

            <AccountFields
              value={account}
              onChange={(next) => {
                setNameErrors((current) => withoutEdited(current, account, next));
                setAccount(next);
              }}
              errors={errors.account}
              emailStatus={<EmailVerifiedText verifiedAt={member.email_verified_at} />}
            />
            <ProfileFieldsets
              value={profile}
              onChange={(next) => setProfile(next)}
              errors={errors.profile}
              darts={darts.data ?? []}
              dartsLoading={darts.isPending}
              audience="administrator"
            />
            <AdminOnlyFields
              value={adminOnly}
              onChange={(next) => setAdminOnly(next)}
              errors={errors.profile}
            />

            <div className="cluster">
              <Button type="submit" disabled={update.isPending}>
                {update.isPending ? 'Saving…' : 'Save changes'}
              </Button>
              <RefusedSubmitNote count={refusal.count} />
            </div>
          </form>
        </Card>
      )}
    </>
  );
}
