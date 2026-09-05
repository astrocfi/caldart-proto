/**
 * The account and profile field groups, shared by "New member" and the
 * Profile tab of a member record so the two forms cannot drift apart.
 *
 * Everything is held as strings while it is being edited — that is what an
 * `<input>` gives you — and `profilePayload` converts back to the API's types
 * on submit.
 */
import { Field } from '../../components';
import type { Dart, Rating } from '../../api/types';
import {
  CERTIFICATE_CHOICES,
  IFR_CHOICES,
  MEDICAL_CHOICES,
  RATING_CHOICES,
  VOLUNTEER_FIELDS,
} from './choices';
import type { VolunteerField } from './choices';
import type { AdminProfile, AdminProfilePayload } from './types';

export interface AccountDraft {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  is_active: boolean;
}

export interface ProfileDraft {
  phone: string;
  phone_alt: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  county: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  home_airport_identifier: string;
  home_airport_city: string;
  dart: string;
  air_care_alliance_number: string;
  pilot_certificate_type: string;
  certificate_number: string;
  ifr_rated: string;
  ratings: Rating[];
  medical_type: string;
  medical_expiration: string;
  flight_review_date: string;
  total_hours: string;
  vol_ground_team: boolean;
  vol_exercise_training: boolean;
  vol_member_support: boolean;
  vol_fundraising: boolean;
  vol_social_media: boolean;
  vol_newsletter: boolean;
  notes: string;
  how_heard: string;
}

export function emptyAccountDraft(): AccountDraft {
  return { email: '', first_name: '', last_name: '', password: '', is_active: true };
}

export function emptyProfileDraft(): ProfileDraft {
  return {
    phone: '',
    phone_alt: '',
    address_line1: '',
    address_line2: '',
    city: '',
    state: 'CA',
    postal_code: '',
    county: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    home_airport_identifier: '',
    home_airport_city: '',
    dart: '',
    air_care_alliance_number: '',
    pilot_certificate_type: 'none',
    certificate_number: '',
    ifr_rated: 'na',
    ratings: [],
    medical_type: 'none',
    medical_expiration: '',
    flight_review_date: '',
    total_hours: '',
    vol_ground_team: false,
    vol_exercise_training: false,
    vol_member_support: false,
    vol_fundraising: false,
    vol_social_media: false,
    vol_newsletter: false,
    notes: '',
    how_heard: '',
  };
}

/** Fill a draft from the record the API returned. */
export function profileDraft(profile: AdminProfile | null): ProfileDraft {
  const draft = emptyProfileDraft();
  if (!profile) return draft;
  return {
    ...draft,
    ...profile,
    dart: profile.dart ? String(profile.dart.id) : '',
    medical_expiration: profile.medical_expiration ?? '',
    flight_review_date: profile.flight_review_date ?? '',
    total_hours: profile.total_hours === null ? '' : String(profile.total_hours),
    ratings: profile.ratings ?? [],
  };
}

/** Convert a draft back into the JSON the API expects. */
export function profilePayload(draft: ProfileDraft): AdminProfilePayload {
  return {
    phone: draft.phone,
    phone_alt: draft.phone_alt,
    address_line1: draft.address_line1,
    address_line2: draft.address_line2,
    city: draft.city,
    state: draft.state,
    postal_code: draft.postal_code,
    county: draft.county,
    emergency_contact_name: draft.emergency_contact_name,
    emergency_contact_phone: draft.emergency_contact_phone,
    home_airport_identifier: draft.home_airport_identifier,
    home_airport_city: draft.home_airport_city,
    dart: draft.dart ? Number(draft.dart) : null,
    air_care_alliance_number: draft.air_care_alliance_number,
    pilot_certificate_type:
      draft.pilot_certificate_type as AdminProfilePayload['pilot_certificate_type'],
    certificate_number: draft.certificate_number,
    ifr_rated: draft.ifr_rated as AdminProfilePayload['ifr_rated'],
    ratings: draft.ratings,
    medical_type: draft.medical_type as AdminProfilePayload['medical_type'],
    medical_expiration: draft.medical_expiration || null,
    flight_review_date: draft.flight_review_date || null,
    total_hours: draft.total_hours === '' ? null : Number(draft.total_hours),
    vol_ground_team: draft.vol_ground_team,
    vol_exercise_training: draft.vol_exercise_training,
    vol_member_support: draft.vol_member_support,
    vol_fundraising: draft.vol_fundraising,
    vol_social_media: draft.vol_social_media,
    vol_newsletter: draft.vol_newsletter,
    notes: draft.notes,
    how_heard: draft.how_heard,
  };
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
  value: ProfileDraft;
  onChange: (next: ProfileDraft) => void;
  errors?: FieldErrors;
  darts: Dart[];
}

export function ProfileFields({ value, onChange, errors = {}, darts }: ProfileFieldsProps) {
  const set = <Key extends keyof ProfileDraft>(key: Key, next: ProfileDraft[Key]) =>
    onChange({ ...value, [key]: next });

  const toggleRating = (rating: Rating, checked: boolean) =>
    set(
      'ratings',
      checked ? [...value.ratings, rating] : value.ratings.filter((item) => item !== rating),
    );

  const text = <Key extends keyof ProfileDraft>(
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
          onChange={(event) => set(key, event.target.value as ProfileDraft[Key])}
        />
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
          <div className="col-half">{text('county', 'County')}</div>
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
            <Field label="DART" error={errors.dart}>
              {(props) => (
                <select
                  {...props}
                  value={value.dart}
                  onChange={(event) => set('dart', event.target.value)}
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
            <Field label="Pilot certificate" error={errors.pilot_certificate_type}>
              {(props) => (
                <select
                  {...props}
                  value={value.pilot_certificate_type}
                  onChange={(event) => set('pilot_certificate_type', event.target.value)}
                >
                  {CERTIFICATE_CHOICES.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <div className="col-half">{text('certificate_number', 'Certificate number')}</div>
          <div className="col-half">
            <Field label="Instrument rated" error={errors.ifr_rated}>
              {(props) => (
                <select
                  {...props}
                  value={value.ifr_rated}
                  onChange={(event) => set('ifr_rated', event.target.value)}
                >
                  {IFR_CHOICES.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <div className="col-half">
            <Field label="Medical" error={errors.medical_type}>
              {(props) => (
                <select
                  {...props}
                  value={value.medical_type}
                  onChange={(event) => set('medical_type', event.target.value)}
                >
                  {MEDICAL_CHOICES.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <div className="col-half">{text('medical_expiration', 'Medical expiration', 'date')}</div>
          <div className="col-half">{text('flight_review_date', 'Flight review', 'date')}</div>
          <div className="col-half">{text('total_hours', 'Total hours', 'number')}</div>
        </div>

        <fieldset>
          <legend>Ratings</legend>
          <div className="cluster">
            {RATING_CHOICES.map((choice) => (
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
          {VOLUNTEER_FIELDS.map((entry) => (
            <label key={entry.name}>
              <input
                type="checkbox"
                checked={value[entry.name as VolunteerField]}
                onChange={(event) => set(entry.name, event.target.checked)}
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
              value={value.how_heard}
              onChange={(event) => set('how_heard', event.target.value)}
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
              onChange={(event) => set('notes', event.target.value)}
            />
          )}
        </Field>
      </fieldset>
    </>
  );
}
