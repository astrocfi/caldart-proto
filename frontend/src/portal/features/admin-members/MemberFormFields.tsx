/**
 * The account and profile field groups, shared by "New member" and the
 * Profile tab of a member record so the two forms cannot drift apart.
 *
 * The profile half *is* the member's own form state: `ProfileFormValues`,
 * `profileToForm` and `formToPatch` from `features/profile/form`, so an
 * administrator and a member are editing one definition of a profile and
 * converting it to the wire the same way.  Only the two admin-only fields are
 * extra, and they live in their own small draft.
 *
 * The markup differs from `<ProfileForm/>` deliberately: an administrator gets
 * a two-column layout, the account fields, the admin-only fieldset, and no
 * client-side insistence that a half-known record be completed.  The server's
 * rules still apply to both.
 */
import { Field } from '../../components';
import type { Dart } from '../../api/types';
import type { ProfileFormValues } from '../profile/form';
import {
  CA_COUNTIES,
  CERTIFICATE_TYPES,
  IFR_OPTIONS,
  MEDICAL_TYPES,
  RATINGS,
  VOLUNTEER_INTERESTS,
} from './choices';
import type { AdminProfile, AdminProfilePayload } from './types';

export interface AccountDraft {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  is_active: boolean;
}

/** The two fields only an administrator sees (PLAN §4.2). */
export interface AdminOnlyDraft {
  notes: string;
  how_heard: string;
}

export const EMPTY_ADMIN_ONLY: AdminOnlyDraft = { notes: '', how_heard: '' };

export function emptyAccountDraft(): AccountDraft {
  return { email: '', first_name: '', last_name: '', password: '', is_active: true };
}

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

export function AccountFields({
  value,
  onChange,
  errors = {},
  withPassword = false,
  withActive = false,
}: AccountFieldsProps) {
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

export interface ProfileFieldsProps {
  value: ProfileFormValues;
  onChange: (next: ProfileFormValues) => void;
  adminOnly: AdminOnlyDraft;
  onAdminOnlyChange: (next: AdminOnlyDraft) => void;
  errors?: FieldErrors;
  darts: Dart[];
}

export function ProfileFields({
  value,
  onChange,
  adminOnly,
  onAdminOnlyChange,
  errors = {},
  darts,
}: ProfileFieldsProps) {
  const set = <Key extends keyof ProfileFormValues>(key: Key, next: ProfileFormValues[Key]) =>
    onChange({ ...value, [key]: next });

  const toggleRating = (rating: ProfileFormValues['ratings'][number], checked: boolean) =>
    set(
      'ratings',
      checked ? [...value.ratings, rating] : value.ratings.filter((item) => item !== rating),
    );

  const text = <Key extends keyof ProfileFormValues>(
    key: Key,
    label: string,
    type = 'text',
    autoComplete?: string,
  ) => (
    <Field label={label} error={errors[key]}>
      {(props) => (
        <input
          {...props}
          type={type}
          autoComplete={autoComplete}
          value={String(value[key] ?? '')}
          onChange={(event) => set(key, event.target.value as ProfileFormValues[Key])}
        />
      )}
    </Field>
  );

  const choose = <Key extends keyof ProfileFormValues>(
    key: Key,
    label: string,
    options: readonly { value: string; label: string }[],
  ) => (
    <Field label={label} error={errors[key]}>
      {(props) => (
        <select
          {...props}
          value={String(value[key] ?? '')}
          onChange={(event) => set(key, event.target.value as ProfileFormValues[Key])}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );

  return (
    <>
      <fieldset>
        <legend>Contact</legend>
        <div className="grid">
          <div className="col-half">{text('phone', 'Phone', 'tel', 'tel')}</div>
          <div className="col-half">{text('phone_alt', 'Alternate phone', 'tel')}</div>
          <div className="col-half">
            {text('address_line1', 'Address', 'text', 'address-line1')}
          </div>
          <div className="col-half">
            {text('address_line2', 'Address line 2', 'text', 'address-line2')}
          </div>
          <div className="col-half">{text('city', 'City', 'text', 'address-level2')}</div>
          <div className="col-half">{text('state', 'State', 'text', 'address-level1')}</div>
          <div className="col-half">{text('postal_code', 'ZIP code', 'text', 'postal-code')}</div>
          <div className="col-half">
            <Field label="County" error={errors.county}>
              {(props) => (
                <input
                  {...props}
                  type="text"
                  list="admin-member-counties"
                  value={value.county}
                  onChange={(event) => set('county', event.target.value)}
                />
              )}
            </Field>
            <datalist id="admin-member-counties">
              {CA_COUNTIES.map((county) => (
                <option key={county} value={county} />
              ))}
            </datalist>
          </div>
          <div className="col-half">{text('emergency_contact_name', 'Emergency contact')}</div>
          <div className="col-half">
            {text('emergency_contact_phone', 'Emergency contact phone', 'tel')}
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>Aviation</legend>
        <div className="grid">
          <div className="col-half">
            {text('home_airport_identifier', 'Home airport identifier')}
          </div>
          <div className="col-half">{text('home_airport_city', 'Home airport city')}</div>
          <div className="col-half">
            <Field label="DART" error={errors.dart_id}>
              {(props) => (
                <select
                  {...props}
                  value={value.dart_id}
                  onChange={(event) => set('dart_id', event.target.value)}
                >
                  <option value="">Unaffiliated</option>
                  {darts.map((dart) => (
                    <option key={dart.id} value={String(dart.id)}>
                      {dart.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <div className="col-half">
            {text('air_care_alliance_number', 'Air Care Alliance number')}
          </div>
          <div className="col-half">
            {choose('pilot_certificate_type', 'Pilot certificate', CERTIFICATE_TYPES)}
          </div>
          <div className="col-half">{text('certificate_number', 'Certificate number')}</div>
          <div className="col-half">{choose('ifr_rated', 'Instrument rated', IFR_OPTIONS)}</div>
          <div className="col-half">{choose('medical_type', 'Medical', MEDICAL_TYPES)}</div>
          <div className="col-half">{text('medical_expiration', 'Medical expiration', 'date')}</div>
          <div className="col-half">{text('flight_review_date', 'Flight review', 'date')}</div>
          <div className="col-half">{text('total_hours', 'Total hours', 'number')}</div>
        </div>

        <fieldset>
          <legend>Ratings</legend>
          <div className="cluster">
            {RATINGS.map((choice) => (
              <label key={choice.value}>
                <input
                  type="checkbox"
                  checked={value.ratings.includes(choice.value)}
                  onChange={(event) => toggleRating(choice.value, event.target.checked)}
                />{' '}
                {choice.label}
              </label>
            ))}
          </div>
        </fieldset>
      </fieldset>

      <fieldset>
        <legend>Volunteer interests</legend>
        <div className="cluster">
          {VOLUNTEER_INTERESTS.map((entry) => (
            <label key={entry.field}>
              <input
                type="checkbox"
                checked={value[entry.field]}
                onChange={(event) => set(entry.field, event.target.checked)}
              />{' '}
              {entry.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Administration</legend>
        <Field label="How they heard about CalDART" error={errors.how_heard}>
          {(props) => (
            <input
              {...props}
              type="text"
              value={adminOnly.how_heard}
              onChange={(event) =>
                onAdminOnlyChange({ ...adminOnly, how_heard: event.target.value })
              }
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
              value={adminOnly.notes}
              onChange={(event) => onAdminOnlyChange({ ...adminOnly, notes: event.target.value })}
            />
          )}
        </Field>
      </fieldset>
    </>
  );
}
