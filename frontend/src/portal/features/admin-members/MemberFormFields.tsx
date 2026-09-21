/**
 * The field groups an administrator gets on top of the profile itself, shared
 * by "New member" and the Profile tab of a member record.
 *
 * The profile fields are `<ProfileFieldsets/>` from `features/profile`, the
 * very ones the member fills in at `/profile`, editing the same
 * `ProfileFormValues` and converting to the wire through the same
 * `formToPatch`.  What an administrator adds is the account itself and the two
 * fields only they can read, and those are the components here.
 *
 * Administrator screens render the profile fieldsets without required markers
 * and do no client-side insistence that a half-known record be completed.  The
 * server's rules still apply to both.
 */
import type { JSX } from 'react';

import { Field } from '../../components';
import type { AdminProfile, AdminProfilePayload } from '../../api/types';

export interface AccountDraft {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  is_active: boolean;
}

/** The two fields only an administrator sees. */
export interface AdminOnlyDraft {
  notes: string;
  how_heard: string;
}

export const EMPTY_ADMIN_ONLY: AdminOnlyDraft = { notes: '', how_heard: '' };

/** A blank account draft for the "New member" form, active by default. */
export function emptyAccountDraft(): AccountDraft {
  return { email: '', first_name: '', last_name: '', password: '', is_active: true };
}

/** The admin-only draft for a member's profile, or a blank one when there is none yet. */
export function adminOnlyDraft(profile: AdminProfile | null): AdminOnlyDraft {
  if (!profile) return { ...EMPTY_ADMIN_ONLY };
  return { notes: profile.notes, how_heard: profile.how_heard };
}

/** The profile half of the request body: the member's patch plus the extras. */
export function adminProfilePayload(
  patch: AdminProfilePayload,
  extra: AdminOnlyDraft,
): AdminProfilePayload {
  return { ...patch, notes: extra.notes, how_heard: extra.how_heard };
}

export type FieldErrors = Record<string, string>;

export interface AccountFieldsProps {
  value: AccountDraft;
  onChange: (next: AccountDraft) => void;
  errors?: FieldErrors;
  /** Offer a password box (creation only; changing one is the member's own job). */
  withPassword?: boolean;
  /** Offer the active/inactive switch (editing only). */
  withActive?: boolean;
}

/** The account fieldset: email, name, and optionally a password and active switch. */
export function AccountFields({
  value,
  onChange,
  errors = {},
  withPassword = false,
  withActive = false,
}: AccountFieldsProps): JSX.Element {
  const set = <Key extends keyof AccountDraft>(key: Key, next: AccountDraft[Key]) =>
    onChange({ ...value, [key]: next });

  return (
    <fieldset>
      <legend>Account</legend>
      <div className="grid">
        <div className="col-half">
          <Field label="Email address" required error={errors.email}>
            {(props) => (
              <input
                {...props}
                type="email"
                autoComplete="email"
                value={value.email}
                onChange={(event) => set('email', event.target.value)}
              />
            )}
          </Field>
        </div>
        <div className="col-half">
          <Field label="First name" error={errors.first_name}>
            {(props) => (
              <input
                {...props}
                type="text"
                value={value.first_name}
                onChange={(event) => set('first_name', event.target.value)}
              />
            )}
          </Field>
        </div>
        <div className="col-half">
          <Field label="Last name" error={errors.last_name}>
            {(props) => (
              <input
                {...props}
                type="text"
                value={value.last_name}
                onChange={(event) => set('last_name', event.target.value)}
              />
            )}
          </Field>
        </div>
        {withPassword ? (
          <div className="col-half">
            <Field
              label="Password"
              error={errors.password}
              hint="Leave blank to email an invitation to set one."
            >
              {(props) => (
                <input
                  {...props}
                  type="password"
                  autoComplete="new-password"
                  value={value.password}
                  onChange={(event) => set('password', event.target.value)}
                />
              )}
            </Field>
          </div>
        ) : null}
      </div>
      {withActive ? (
        <label>
          <input
            type="checkbox"
            checked={value.is_active}
            onChange={(event) => set('is_active', event.target.checked)}
          />{' '}
          Account is active
        </label>
      ) : null}
    </fieldset>
  );
}

export interface AdminOnlyFieldsProps {
  value: AdminOnlyDraft;
  onChange: (next: AdminOnlyDraft) => void;
  errors?: FieldErrors;
}

/**
 * The Administration fieldset: how the member heard about CalDART, and the
 * notes only account administrators can read.  Members never see either, on
 * any screen.
 *
 * @param value - the draft being edited; the component holds no state of its own.
 * @param onChange - called with the whole next draft on every edit.
 */
export function AdminOnlyFields({
  value,
  onChange,
  errors = {},
}: AdminOnlyFieldsProps): JSX.Element {
  return (
    <fieldset>
      <legend>Administration</legend>
      <Field label="How they heard about CalDART" error={errors.how_heard}>
        {(props) => (
          <input
            {...props}
            type="text"
            value={value.how_heard}
            onChange={(event) => onChange({ ...value, how_heard: event.target.value })}
          />
        )}
      </Field>
      <Field
        label="Administrator notes"
        hint="Only account administrators can read these."
        error={errors.notes}
      >
        {(props) => (
          <textarea
            {...props}
            value={value.notes}
            onChange={(event) => onChange({ ...value, notes: event.target.value })}
          />
        )}
      </Field>
    </fieldset>
  );
}
