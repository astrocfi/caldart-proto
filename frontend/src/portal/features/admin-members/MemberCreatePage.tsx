/**
 * `/admin/members/new` — create an account and its profile in one request.
 *
 * Leaving the password blank is the normal path: the server stores an unusable
 * password and emails the new member a link to choose their own.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { useNavigate } from 'react-router-dom';

import { useDarts } from '@/portal/api/queries';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { ProfileFieldsets } from '@/portal/features/profile/ProfileFieldsets';
import { EMPTY_PROFILE_FORM, formToPatch } from '@/portal/features/profile/form';
import {
  AccountFields,
  AdminOnlyFields,
  EMPTY_ADMIN_ONLY,
  adminProfilePayload,
  emptyAccountDraft,
} from './MemberFormFields';
import { useCreateMember } from './api';
import { splitErrors } from './errors';

/** `/admin/members/new` page: create a member account and profile in one request. */
export function MemberCreatePage(): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const darts = useDarts();
  const create = useCreateMember();

  const [account, setAccount] = useState(emptyAccountDraft);
  const [profile, setProfile] = useState(EMPTY_PROFILE_FORM);
  const [adminOnly, setAdminOnly] = useState(EMPTY_ADMIN_ONLY);

  const errors = splitErrors(create.error);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    create.mutate(
      {
        email: account.email.trim(),
        first_name: account.first_name,
        last_name: account.last_name,
        ...(account.password ? { password: account.password } : {}),
        profile: adminProfilePayload(formToPatch(profile), adminOnly),
      },
      {
        onSuccess: (member) => {
          toast.show(
            account.password
              ? `${member.name} can sign in now.`
              : `${member.name} has been emailed a link to set a password.`,
            'success',
          );
          void navigate(`/admin/members/${member.id}`);
        },
      },
    );
  };

  return (
    <Page
      title="New member"
      eyebrow="Administration"
      lede="Create an account and fill in as much of the profile as you have."
      actions={
        <ButtonLink to="/admin/members" variant="quiet">
          Back to members
        </ButtonLink>
      }
    >
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
            withPassword
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
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Create member'}
            </Button>
            <ButtonLink to="/admin/members" variant="quiet">
              Cancel
            </ButtonLink>
          </div>
        </form>
      </Card>
    </Page>
  );
}
