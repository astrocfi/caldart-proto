/** `/admin/users/:id` — edit one account's names, email, roles, and status. */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { RoleSlug, User } from '@/portal/api/types';
import { useAuth, useRoles } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { MembershipChip } from '@/portal/components/StatusChip';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { EMAIL_MESSAGE, isEmailAddress, maskEmail } from '@/portal/masks';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { useAdminUser, useSendPasswordReset, useUpdateAdminUser } from './api';

interface FormState {
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
  roles: RoleSlug[];
}

function formFor(user: User): FormState {
  return {
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email,
    is_active: user.is_active,
    roles: user.roles,
  };
}

function displayName(user: User): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

/** `/admin/users/:id` page: edit one account's names, email, roles, and status. */
export function UserDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const query = useAdminUser(id);
  const roles = useRoles();
  const update = useUpdateAdminUser(id);
  const sendReset = useSendPasswordReset(id);
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
          <MembershipChip membership={user.membership} />
          <span className="muted">
            {user.profile_complete ? 'Profile complete' : 'Profile incomplete'}
          </span>
        </div>
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
            hint="This is also how they sign in."
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

          <fieldset>
            <legend>Account status</legend>
            <label className="cluster">
              <input
                type="checkbox"
                name="is_active"
                checked={form.is_active}
                disabled={isSelf}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              <span>Active — the account can sign in</span>
            </label>
            {isSelf ? <p className="field__hint">You cannot deactivate your own account.</p> : null}
            {fieldError(update.error, 'is_active') ? (
              <p className="field__error" role="alert">
                {fieldError(update.error, 'is_active')}
              </p>
            ) : null}
          </fieldset>

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
                    <span>{role.slug.replace(/_/g, ' ')}</span>
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

          <FormAlert
            error={update.error}
            handled={['first_name', 'last_name', 'email', 'is_active', 'roles']}
          />

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
    </Page>
  );
}
