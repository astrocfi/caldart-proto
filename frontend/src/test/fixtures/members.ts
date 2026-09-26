/** Test fixtures for the members-admin screens. */
import type { MemberDetail, MemberRow, MembershipStatus } from '@/portal/api/types';

export const CURRENT: MembershipStatus = {
  status: 'current',
  expires_on: '2027-06-30',
  plan: 'Annual',
  is_lifetime: false,
};

export const LIFETIME: MembershipStatus = {
  status: 'current',
  expires_on: null,
  plan: 'Life',
  is_lifetime: true,
};

/** Builds a member list row for tests, with `overrides` replacing any default field. */
export function makeRow(overrides: Partial<MemberRow> = {}): MemberRow {
  return {
    user_id: 1,
    name: 'Ana Bracco',
    email: 'ana@example.org',
    phone: '415-555-0100',
    dart: 'Palo Alto',
    is_active: true,
    membership: CURRENT,
    pilot_certificate_type: 'private',
    medical_type: 'third',
    medical_expiration: '2027-01-31',
    medical_is_current: true,
    aircraft: ['N172SP'],
    joined_on: '2024-07-01',
    profile_updated_at: '2026-08-11T09:14:02.100522-07:00',
    ...overrides,
  };
}

/** Builds a member detail record for tests, with `overrides` replacing any default field. */
export function makeDetail(overrides: Partial<MemberDetail> = {}): MemberDetail {
  return {
    id: 1,
    email: 'ana@example.org',
    first_name: 'Ana',
    last_name: 'Bracco',
    name: 'Ana Bracco',
    is_active: true,
    roles: ['member'],
    created_at: '2024-07-01T12:00:00Z',
    email_verified_at: '2024-07-01T12:05:00Z',
    joined_on: '2024-07-01',
    profile_updated_at: '2026-08-11T09:14:02.100522-07:00',
    membership: CURRENT,
    profile: {
      phone: '415-555-0100',
      phone_extension: '',
      phone_alt_extension: '',
      emergency_contact_phone_extension: '',
      phone_alt: '',
      address_line1: '1 Airport Way',
      address_line2: '',
      city: 'Palo Alto',
      state: 'CA',
      postal_code: '94303',
      county: 'Santa Clara',
      emergency_contact_name: 'Bo Bracco',
      emergency_contact_phone: '415-555-0101',
      member_since: null,
      home_airport_identifier: 'PAO',
      home_airport_city: 'Palo Alto',
      dart: { id: 3, name: 'Palo Alto' },
      air_care_alliance_number: '',
      pilot_certificate_type: 'private',
      certificate_number: '1234567',
      ifr_rated: 'yes',
      ratings: ['instrument'],
      medical_type: 'third',
      medical_expiration: '2027-01-31',
      medical_is_current: true,
      flight_review_date: '2026-02-01',
      total_hours: 750,
      aircraft: [
        {
          id: 9,
          n_number: 'N172SP',
          make: 'Cessna',
          model: '172S',
          insurance_is_current: true,
          insurance_expiration: '2027-03-01',
          insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
        },
      ],
      flies_rented_aircraft: false,
      vol_mission_pilot: false,
      vol_ground_team: true,
      vol_exercise_training: false,
      vol_member_support: false,
      vol_fundraising: false,
      vol_social_media: false,
      vol_newsletter: false,
      notes: 'Called about the Napa exercise.',
      how_heard: 'EAA chapter meeting',
    },
    memberships: [
      {
        id: 11,
        plan: 'Annual',
        plan_slug: 'annual',
        starts_on: '2026-07-01',
        ends_on: '2027-06-30',
        status: 'active',
        source: 'payment',
        note: '',
        granted_by: null,
        payment: 21,
        created_at: '2026-07-01T12:00:00Z',
      },
    ],
    payments: [
      {
        id: 21,
        plan: 'Annual',
        amount_cents: 6500,
        plan_amount_cents: 4500,
        contribution_cents: 2000,
        currency: 'usd',
        provider: 'stripe',
        wallet: 'card',
        provider_ref: 'pi_123',
        status: 'succeeded',
        created_at: '2026-07-01T12:00:00Z',
        completed_at: '2026-07-01T12:00:05Z',
      },
    ],
    ...overrides,
  };
}
