/**
 * `/admin/members/new` — create an account and its profile in one request.
 *
 * Leaving the password blank is the normal path: the server stores an unusable
 * password and emails the new member a link to choose their own.
 */
import { useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useDarts } from '@/portal/api/queries';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { FOCUS_TITLE, Page } from '@/portal/components/Page';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { useToast } from '@/portal/components/Toast';
import { ProfileFieldsets } from '@/portal/features/profile/ProfileFieldsets';
import { EMPTY_PROFILE_FORM, formToPatch } from '@/portal/features/profile/form';
import {
  AccountFields,
  AdminOnlyFields,
  EMPTY_ADMIN_ONLY,
  adminProfilePayload,
  emailProblem,
  emptyAccountDraft,
  kindPayload,
  missingNames,
  withoutEdited,
} from './MemberFormFields';
import type { FieldErrors } from './MemberFormFields';
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

  // The complaints found before sending anything: the address and the names.
  const [localErrors, setLocalErrors] = useState<FieldErrors>({});

  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, create.error);
  const server = splitErrors(create.error);
  // A server error for a field goes once that field is edited.
  const freshAccount = useFreshErrors(create.error, account, server.account);
  const freshProfile = useFreshErrors(create.error, { ...profile, ...adminOnly }, server.profile);
  const errors = {
    ...server,
    account: { ...freshAccount, ...localErrors },
    profile: freshProfile,
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const found: FieldErrors = missingNames(account);
    const emailError = emailProblem(account.email);
    if (emailError !== null) found.email = emailError;
    setLocalErrors(found);
    if (Object.keys(found).length > 0) {
      refusal.refuse();
      return;
    }
    create.mutate(
      {
        email: account.email.trim(),
        first_name: account.first_name,
        last_name: account.last_name,
        ...(account.password ? { password: account.password } : {}),
        ...kindPayload(account),
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
          // The form goes with the move, so the record's title takes the focus.
          void navigate(`/admin/members/${member.id}`, { state: FOCUS_TITLE });
        },
      },
    );
  };

  return (
    <Page
      title="New member"
      lede="Create an account and fill in as much of the profile as you have."
      actions={<Link to="/admin/members">Back to members</Link>}
    >
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
              setLocalErrors((current) => withoutEdited(current, account, next));
              setAccount(next);
            }}
            errors={errors.account}
            withPassword
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
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Adding…' : 'Add member'}
            </Button>
            <ButtonLink to="/admin/members" variant="quiet">
              Cancel
            </ButtonLink>
            <RefusedSubmitNote count={refusal.count} />
          </div>
        </form>
      </Card>
    </Page>
  );
}
