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
 * account is the exception: its email address and both names are required, here and
 * on the server, so no record is saved under a surname alone.  The server's rules
 * still apply to both.
 */
import type { JSX, ReactNode } from 'react';

import type {
  AccountKind,
  AdminProfile,
  AdminProfilePayload,
  PersonKind,
} from '@/portal/api/types';
import { ACCOUNT_KIND_LABELS } from '@/portal/choices';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { maskEmail } from '@/portal/masks';

export interface AccountDraft {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  /** A donor's kind is shown elsewhere and never edited here. */
  kind: AccountKind;
}

/** The kinds an administrator may choose between: never a donor. */
const PERSON_KINDS: PersonKind[] = ['member', 'friend'];

/**
 * The `kind` a member write should carry for `draft`: the chosen kind, or nothing
 * for a donor, whose kind an administrator never changes.
 */
export function kindPayload(draft: AccountDraft): { kind?: PersonKind } {
  return draft.kind === 'donor' ? {} : { kind: draft.kind };
}

/** The two fields only an administrator sees. */
export interface AdminOnlyDraft {
  notes: string;
  how_heard: string;
}

export const EMPTY_ADMIN_ONLY: AdminOnlyDraft = { notes: '', how_heard: '' };

/** A blank account draft for the "New member" form: an active member by default. */
export function emptyAccountDraft(): AccountDraft {
  return {
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    kind: 'member',
  };
}

/** The admin-only draft for a member's profile, or a blank one when there is none yet. */
export function adminOnlyDraft(profile: AdminProfile | null): AdminOnlyDraft {
  if (!profile) return { ...EMPTY_ADMIN_ONLY };
  return { notes: profile.notes, how_heard: profile.how_heard };
}

/**
 * The profile half of the request body: the member's patch, the photo ID with it, plus
 * the extras.
 */
export function adminProfilePayload<Patch extends AdminProfilePayload>(
  patch: Patch,
  extra: AdminOnlyDraft,
): Patch & AdminOnlyDraft {
  return { ...patch, notes: extra.notes, how_heard: extra.how_heard };
}

export type FieldErrors = Record<string, string>;

/** What a blank name is refused with, in the server's own words. */
const NAME_MESSAGES = {
  first_name: 'Enter a first name.',
  last_name: 'Enter a last name.',
} as const;

/**
 * The complaints about `draft`'s names: each one left blank, as the server would refuse
 * it, so a record never saves under a surname alone.
 */
export function missingNames(draft: AccountDraft): FieldErrors {
  const errors: FieldErrors = {};
  for (const key of ['first_name', 'last_name'] as const) {
    if (draft[key].trim() === '') errors[key] = NAME_MESSAGES[key];
  }
  return errors;
}

/** `errors` less the ones about fields whose value differs between `before` and `after`. */
export function withoutEdited(
  errors: FieldErrors,
  before: AccountDraft,
  after: AccountDraft,
): FieldErrors {
  return Object.fromEntries(
    Object.entries(errors).filter(
      ([key]) =>
        !(key in after) || before[key as keyof AccountDraft] === after[key as keyof AccountDraft],
    ),
  );
}

export interface AccountFieldsProps {
  value: AccountDraft;
  onChange: (next: AccountDraft) => void;
  errors?: FieldErrors;
  /** Offer a password box (creation only; changing one is the member's own job). */
  withPassword?: boolean;
  /** A standing fact under the email box, such as whether the address is verified. */
  emailStatus?: ReactNode;
}

/**
 * The account fieldset: email, name, the kind of account (member or friend; a
 * donor's is left alone), and optionally a password.
 */
export function AccountFields({
  value,
  onChange,
  errors = {},
  withPassword = false,
  emailStatus,
}: AccountFieldsProps): JSX.Element {
  const set = <Key extends keyof AccountDraft>(key: Key, next: AccountDraft[Key]) =>
    onChange({ ...value, [key]: next });

  return (
    <fieldset>
      <legend>Account</legend>
      <div className="form-grid">
        <Field label="Email address" required error={errors.email} status={emailStatus}>
          {(props) => (
            <MaskedInput
              {...props}
              type="email"
              autoComplete="email"
              mask={maskEmail}
              value={value.email}
              onValueChange={(next) => set('email', next)}
            />
          )}
        </Field>
        <Field label="First name" required error={errors.first_name}>
          {(props) => (
            <input
              {...props}
              type="text"
              value={value.first_name}
              onChange={(event) => set('first_name', event.target.value)}
            />
          )}
        </Field>
        <Field label="Last name" required error={errors.last_name}>
          {(props) => (
            <input
              {...props}
              type="text"
              value={value.last_name}
              onChange={(event) => set('last_name', event.target.value)}
            />
          )}
        </Field>
        {value.kind === 'donor' ? null : (
          <Field
            label="Kind of account"
            error={errors.kind}
            hint="A friend pays no dues and is never current or expired."
          >
            {(props) => (
              <select
                {...props}
                value={value.kind}
                onChange={(event) => set('kind', event.target.value as PersonKind)}
              >
                {PERSON_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {ACCOUNT_KIND_LABELS[kind]}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        {withPassword ? (
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
        ) : null}
      </div>
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
