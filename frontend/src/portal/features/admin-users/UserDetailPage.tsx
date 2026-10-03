/**
 * `/admin/users/:id` — edit one account's names, email, and roles, and change its
 * status: deactivate or reactivate it, and block it from reactivating or lift the block.
 * An address the bounce check found bouncing carries a **Bounced** chip beside it and a
 * **Clear bounce** action that asks first.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { AdminUser, RoleSlug } from '@/portal/api/types';
import { useAuth, useRoles } from '@/portal/auth/useAuth';
import { ACCOUNT_KIND_LABELS, roleLabel } from '@/portal/choices';
import { BouncedChip } from '@/portal/components/BouncedChip';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { EmailVerifiedText } from '@/portal/components/EmailVerifiedText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { MemberRecordLink } from '@/portal/components/MemberRecordLink';
import { MembershipChip } from '@/portal/components/StatusChip';
import { Page } from '@/portal/components/Page';
import { ResendVerificationButton } from '@/portal/components/ResendVerificationButton';
import { useToast } from '@/portal/components/Toast';
import { EMAIL_MESSAGE, isEmailAddress, maskEmail } from '@/portal/masks';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { AccountStatusCard } from './AccountStatusCard';
import {
  useAdminUser,
  useClearBounce,
  useSendEmailVerification,
  useSendPasswordReset,
  useUpdateAdminUser,
} from './api';

interface FormState {
  first_name: string;
  last_name: string;
  email: string;
  roles: RoleSlug[];
}

function formFor(user: AdminUser): FormState {
  return {
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email,
    roles: user.roles,
  };
}

function displayName(user: AdminUser): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

/** `/admin/users/:id` page: edit one account's names, email, and roles, and its status. */
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
  const [emailError, setEmailError] = useState<string | null>(null);
  const user = query.data;

  // Seed the form once the account has loaded, and again after a save so the
  // inputs show what the server actually stored.
  useEffect(() => {
    if (user) setForm(formFor(user));
  }, [user]);

  if (query.isPending) {
    return (
      <Page title="User record" eyebrow="Administration">
        <p className="muted" role="status">
          Loading…
        </p>
      </Page>
    );
  }

  if (query.isError || !user || !form) {
    return (
      <Page title="User record" eyebrow="Administration">
        <EmptyState
          title="That account could not be loaded"
          description="It may have been deleted. Go back to the list and search again."
          action={<Link to="/admin/users">Back to users</Link>}
        />
      </Page>
    );
  }

  const isSelf = me?.id === user.id;
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
      eyebrow="Users and roles"
      lede={user.email}
      actions={<Link to="/admin/users">Back to users</Link>}
    >
      <Card eyebrow="Membership" title="Where this account stands">
        <div className="cluster">
          <span className="chip chip--neutral">{ACCOUNT_KIND_LABELS[user.kind]}</span>
          <MembershipChip membership={user.membership} />
          <span className="muted">
            {user.profile_complete ? 'Profile complete' : 'Profile incomplete'}
          </span>
          <MemberRecordLink userId={user.id} />
        </div>
        {isDonor ? (
          <p className="muted">
            A donor gave through the public site and cannot sign in. Fix the email address here if a
            receipt went astray.
          </p>
        ) : null}
      </Card>

      <Card title="Account">
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (!isEmailAddress(form.email)) {
              setEmailError(EMAIL_MESSAGE);
              return;
            }
            setEmailError(null);
            update.mutate(form, {
              onSuccess: () => toast.show('Account saved.', 'success'),
            });
          }}
        >
          <Field label="First name" error={fieldError(update.error, 'first_name')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="first_name"
                autoComplete="given-name"
                value={form.first_name}
                onChange={(event) => setForm({ ...form, first_name: event.target.value })}
              />
            )}
          </Field>
          <Field label="Last name" error={fieldError(update.error, 'last_name')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="last_name"
                autoComplete="family-name"
                value={form.last_name}
                onChange={(event) => setForm({ ...form, last_name: event.target.value })}
              />
            )}
          </Field>
          <Field
            label="Email address"
            error={emailError ?? fieldError(update.error, 'email')}
            hint={
              <>
                This is also how they sign in.{' '}
                <EmailVerifiedText verifiedAt={user.email_verified_at} />{' '}
                <BouncedChip bouncedAt={user.email_bounced_at} detail={user.email_bounce_detail} />
              </>
            }
          >
            {(props) => (
              <MaskedInput
                {...props}
                type="email"
                name="email"
                autoComplete="email"
                mask={maskEmail}
                value={form.email}
                onValueChange={(next) => setForm({ ...form, email: next })}
              />
            )}
          </Field>
          {user.email_verified || isDonor ? null : (
            <div className="cluster">
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
                    Clear this only once you know the address works, for instance after confirming
                    it with them. The flag comes back if the next email to it bounces too.
                  </p>
                </ConfirmButton>
              </div>
              <FormAlert error={clearBounce.error} />
            </div>
          )}

          <fieldset>
            <legend>Roles</legend>
            {roles.isPending ? <p className="muted">Loading roles…</p> : null}
            <ul role="list" className="stack">
              {(roles.data ?? []).map((role) => (
                <li key={role.slug}>
                  <label className="cluster">
                    <input
                      type="checkbox"
                      name="roles"
                      value={role.slug}
                      checked={form.roles.includes(role.slug)}
                      onChange={(event) => toggleRole(role.slug, event.target.checked)}
                    />
                    <span>{roleLabel(role.slug)}</span>
                  </label>
                  <p className="field__hint">{role.description}</p>
                </li>
              ))}
            </ul>
            {fieldError(update.error, 'roles') ? (
              <p className="field__error" role="alert">
                {fieldError(update.error, 'roles')}
              </p>
            ) : null}
          </fieldset>

          <FormAlert error={update.error} handled={['first_name', 'last_name', 'email', 'roles']} />

          <div className="cluster">
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
            <Button variant="quiet" onClick={() => setForm(formFor(user))}>
              Reset form
            </Button>
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
    </Page>
  );
}
