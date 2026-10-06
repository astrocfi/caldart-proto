/**
 * `/admin/users/:id` — edit one account's roles and change its status: deactivate or
 * reactivate it, and block it from reactivating or lift the block. The person's name heads
 * the page and their address is the line under it; neither is changed here, but on the
 * member record or by the person. The Roles card opens with whether the address is
 * verified. An address the bounce check found bouncing carries a **Bounced** chip there and
 * a **Clear bounce** action that asks first.  Only a system administrator may give or take
 * away the System administrator role, so its box is grayed out for anybody else, with
 * the reason under it.  The **History** card lists who changed the account's roles or
 * status, and when.
 */
import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { AdminUser, AdminUserDetail, RoleSlug } from '@/portal/api/types';
import { useAuth, useRoles } from '@/portal/auth/useAuth';
import { ACCOUNT_KIND_LABELS, roleLabel } from '@/portal/choices';
import { BouncedDot } from '@/portal/components/BouncedDot';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { EmailVerifiedText } from '@/portal/components/EmailVerifiedText';
import { EmptyState } from '@/portal/components/EmptyState';
import { MemberRecordLink } from '@/portal/components/MemberRecordLink';
import { MembershipSummary } from '@/portal/features/admin-members/MembershipSummary';
import type { MembershipFacts } from '@/portal/features/admin-members/MembershipSummary';
import { Page } from '@/portal/components/Page';
import {
  RefusedSubmitNote,
  useFreshErrors,
  useRefusedSubmit,
} from '@/portal/components/RefusedSubmit';
import { ResendVerificationButton } from '@/portal/components/ResendVerificationButton';
import { useToast } from '@/portal/components/Toast';
import { useFocusAfterSave } from '@/portal/components/focus';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { AccountHistoryCard } from './AccountHistoryCard';
import { AccountStatusCard } from './AccountStatusCard';
import './users.css';
import {
  useAdminUser,
  useClearBounce,
  useSendEmailVerification,
  useSendPasswordReset,
  useUpdateAdminUser,
} from './api';

interface FormState {
  roles: RoleSlug[];
}

function formFor(user: AdminUser): FormState {
  return { roles: user.roles };
}

/** Why the System administrator box is grayed out for anybody who is not one. */
const SYSTEM_ADMIN_ONLY = 'Only a system administrator can give or take away this role.';

/** What the Membership card words the membership by, from the record's term facts. */
function membershipFacts(user: AdminUserDetail): MembershipFacts {
  return {
    kind: user.kind,
    isActive: user.is_active,
    membership: user.membership,
    friendOn: user.friend_on,
    hasTerms: user.has_terms,
    hasSetAside: user.has_suspended_term,
  };
}

function displayName(user: AdminUser): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

/** `/admin/users/:id` page: one account's names and email, its roles, and its status. */
export function UserDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const query = useAdminUser(id);
  const roles = useRoles();
  const update = useUpdateAdminUser(id);
  const sendReset = useSendPasswordReset(id);
  const sendVerification = useSendEmailVerification(id);
  const clearBounce = useClearBounce(id);
  const toast = useToast();
  const { user: me } = useAuth();

  const [form, setForm] = useState<FormState | null>(null);
  const user = query.data;
  const formRef = useRef<HTMLFormElement>(null);
  const refusal = useRefusedSubmit(formRef, update.error);
  useFocusAfterSave(formRef, update.isPending);
  // The server's complaint about a field goes once the field is edited.
  const serverErrors = useFreshErrors(update.error, form ?? {}, {
    roles: fieldError(update.error, 'roles'),
  });

  // Seed the form once the account has loaded, and again after a save so the
  // inputs show what the server actually stored.
  useEffect(() => {
    if (user) setForm(formFor(user));
  }, [user]);

  if (query.isPending) {
    return (
      <Page title="User record">
        <p className="muted" role="status">
          Loading…
        </p>
      </Page>
    );
  }

  if (query.isError || !user || !form) {
    return (
      <Page title="User record">
        <EmptyState
          title="That account didn't load"
          description="It may have been deleted. Go back to the list and search again."
          action={<Link to="/admin/users">Back to Roles and status</Link>}
        />
      </Page>
    );
  }

  const isSelf = me?.id === user.id;
  // The server refuses anybody else a change to this role, so the box says so first.
  const maySetSystemAdmin = me?.roles.includes('system_admin') ?? false;
  // A donor cannot sign in, so neither a password nor a verification link would
  // lead anywhere.
  const isDonor = user.kind === 'donor';

  const toggleRole = (slug: RoleSlug, checked: boolean) => {
    setForm((current) =>
      current === null
        ? current
        : {
            ...current,
            roles: checked
              ? [...current.roles, slug]
              : current.roles.filter((role) => role !== slug),
          },
    );
  };

  return (
    <Page
      title={displayName(user)}
      tabTitle={`${displayName(user)} · User record`}
      lede={user.email}
      actions={<Link to="/admin/users">Back to Roles and status</Link>}
    >
      <Card title="Membership">
        <div className="cluster">
          <span>{ACCOUNT_KIND_LABELS[user.kind]}</span>
          {isDonor ? null : <MembershipSummary facts={membershipFacts(user)} />}
          <span className="muted">
            {user.profile_complete ? 'Profile complete' : 'Profile incomplete'}
          </span>
          <MemberRecordLink userId={user.id} />
        </div>
        {isDonor ? (
          <p className="muted">
            A donor gave through the public site and cannot sign in. If a receipt went astray, an
            account administrator corrects the email address on the member record.
          </p>
        ) : null}
      </Card>

      <Card title="Roles">
        <p className="user-record__email">
          <span className="muted">Email address: </span>
          <EmailVerifiedText verifiedAt={user.email_verified_at} />{' '}
          <BouncedDot bouncedAt={user.email_bounced_at} detail={user.email_bounce_detail} />
        </p>
        {user.email_verified || isDonor ? null : (
          <div className="cluster user-record__resend">
            <ResendVerificationButton
              variant="secondary"
              disabled={!user.is_active}
              mutation={sendVerification}
            />
          </div>
        )}
        {user.email_bounced_at === null ? null : (
          <div className="stack">
            <div className="cluster">
              <ConfirmButton
                label="Clear bounce"
                choices={[
                  {
                    label: 'Clear bounce',
                    onChoose: () =>
                      clearBounce
                        .mutateAsync()
                        .then(() => toast.show('Bounce cleared.', 'success')),
                  },
                ]}
              >
                <p>
                  Clear this only once you know the address works, for instance after confirming it
                  with them. The flag comes back if the next email to it bounces too.
                </p>
              </ConfirmButton>
            </div>
            <FormAlert error={clearBounce.error} />
          </div>
        )}

        <form
          ref={formRef}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            update.mutate(form, {
              onSuccess: () => toast.show('Account saved.', 'success'),
            });
          }}
        >
          <fieldset>
            <legend>Roles</legend>
            {roles.isPending ? <p className="muted">Loading roles…</p> : null}
            <ul role="list" className="stack">
              {(roles.data ?? []).map((role) => {
                const isLocked = role.slug === 'system_admin' && !maySetSystemAdmin;
                return (
                  <li key={role.slug}>
                    <label className="cluster">
                      <input
                        type="checkbox"
                        name="roles"
                        value={role.slug}
                        checked={form.roles.includes(role.slug)}
                        disabled={isLocked}
                        aria-describedby={`role-${role.slug}-hint`}
                        onChange={(event) => toggleRole(role.slug, event.target.checked)}
                      />
                      <span>{roleLabel(role.slug)}</span>
                    </label>
                    <p className="field__hint" id={`role-${role.slug}-hint`}>
                      {role.description}
                      {isLocked ? ` ${SYSTEM_ADMIN_ONLY}` : null}
                    </p>
                  </li>
                );
              })}
            </ul>
            {serverErrors.roles ? (
              <p className="field__error" role="alert">
                {serverErrors.roles}
              </p>
            ) : null}
          </fieldset>

          <FormAlert error={update.error} handled={['roles']} />

          <div className="cluster">
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
            <Button
              variant="quiet"
              onClick={() => {
                // Starting again from the stored account drops what the server said
                // about the edits being thrown away.
                setForm(formFor(user));
                update.reset();
              }}
            >
              Cancel
            </Button>
            <RefusedSubmitNote count={refusal.count} />
          </div>
        </form>
      </Card>

      {isDonor ? null : <AccountStatusCard user={user} isSelf={isSelf} />}

      {isDonor ? null : (
        <Card
          title="Password"
          footer={
            <Button
              variant="secondary"
              disabled={sendReset.isPending || !user.is_active}
              onClick={() =>
                sendReset.mutate(undefined, {
                  onSuccess: (result) => toast.show(result.detail, 'success'),
                  onError: (error) => toast.show(error.message, 'error'),
                })
              }
            >
              {sendReset.isPending ? 'Sending…' : 'Send password reset'}
            </Button>
          }
        >
          <p className="muted">
            {user.is_active
              ? 'Emails a one-time link so they can choose a new password. You never see it.'
              : 'Reactivate the account before sending a reset link.'}
          </p>
        </Card>
      )}

      <AccountHistoryCard userId={user.id} />
    </Page>
  );
}
