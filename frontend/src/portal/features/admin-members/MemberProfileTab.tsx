/**
 * The Profile tab of a member record: the same fields as "New member", plus the
 * administrator-only notes, under a Verification card for the pilot certificate, the
 * medical, and the photo ID. Deactivating the account is the Danger zone tab's. A
 * "Deleted member N" record shows no form: the server refuses every edit to one.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useDarts } from '@/portal/api/queries';
import type { LeaderStatus, MemberDetail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmailVerifiedText } from '@/portal/components/EmailVerifiedText';
import { useToast } from '@/portal/components/Toast';
import { ProfileFieldsets } from '@/portal/features/profile/ProfileFieldsets';
import { EMPTY_PROFILE_FORM, formToPatch, profileToForm } from '@/portal/features/profile/form';
import { MemberVerificationCard } from '@/portal/features/verification/MemberVerificationCard';
import {
  AccountFields,
  AdminOnlyFields,
  adminOnlyDraft,
  adminProfilePayload,
  kindPayload,
} from './MemberFormFields';
import type { AccountDraft } from './MemberFormFields';
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

  const errors = splitErrors(update.error);
  const verified = member.profile;

  /** A verification save may correct the fields the form below holds; take them up. */
  const handleVerified = (status: LeaderStatus): void => {
    setProfile((current) => ({
      ...current,
      pilot_certificate_type: status.certificate.type,
      certificate_number: status.certificate.number,
      medical_type: status.medical.type,
      medical_expiration: status.medical.expiration ?? '',
      photo_id_type: status.photo_id.type,
    }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
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
          onSaved={handleVerified}
        />
      ) : null}
      {member.is_tombstone ? (
        <Card>
          <p className="muted">{TOMBSTONE_NOTE}</p>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} noValidate>
            {errors.detail ? (
              <p role="alert" className="field__error">
                {errors.detail}
              </p>
            ) : null}

            <AccountFields
              value={account}
              onChange={(next) => setAccount(next)}
              errors={errors.account}
              emailHint={<EmailVerifiedText verifiedAt={member.email_verified_at} />}
            />
            <ProfileFieldsets
              value={profile}
              onChange={(next) => setProfile(next)}
              errors={errors.profile}
              darts={darts.data ?? []}
              dartsLoading={darts.isPending}
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
              {member.profile?.aircraft.length ? (
                <p className="muted">
                  Aircraft on file:{' '}
                  {member.profile.aircraft.map((one, index) => (
                    <span key={one.id}>
                      {index > 0 ? ', ' : ''}
                      <Link className="mono" to={`/admin/aircraft/${one.id}`}>
                        {one.n_number}
                      </Link>
                    </span>
                  ))}
                </p>
              ) : null}
            </div>
          </form>
        </Card>
      )}
    </>
  );
}
