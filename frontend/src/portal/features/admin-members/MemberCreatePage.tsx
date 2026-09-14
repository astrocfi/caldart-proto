/**
 * `/admin/members/new` — create an account and its profile in one request.
 *
 * Leaving the password blank is the normal path: the server stores an unusable
 * password and emails the new member a link to choose their own.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, ButtonLink, Card, Page, useToast } from '../../components';
import { EMPTY_PROFILE_FORM, formToPatch } from '../profile/form';
import {
  AccountFields,
  EMPTY_ADMIN_ONLY,
  ProfileFields,
  adminProfilePayload,
  emptyAccountDraft,
} from './MemberFormFields';
import { useCreateMember, useDarts } from './api';
import { splitErrors } from './errors';

export function MemberCreatePage() {
  const navigate = useNavigate();
  const toast = useToast();
  const darts = useDarts();
  const create = useCreateMember();

  const [account, setAccount] = useState(emptyAccountDraft);
  const [profile, setProfile] = useState(EMPTY_PROFILE_FORM);
  const [adminOnly, setAdminOnly] = useState(EMPTY_ADMIN_ONLY);

  const errors = splitErrors(create.error);

  const submit = (event: React.FormEvent) => {
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
          navigate(`/admin/members/${member.id}`);
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
        <form onSubmit={submit} noValidate>
          {errors.detail ? (
            <p role="alert" className="field__error">
              {errors.detail}
            </p>
          ) : null}

          <AccountFields
            value={account}
            onChange={setAccount}
            errors={errors.account}
            withPassword
          />
          <ProfileFields
            value={profile}
            onChange={setProfile}
            adminOnly={adminOnly}
            onAdminOnlyChange={setAdminOnly}
            errors={errors.profile}
            darts={darts.data ?? []}
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
