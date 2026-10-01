/** Test data for the profile, join, and dashboard suites.  Not shipped. */
import type { AircraftSummary, AircraftType, Dart, Profile } from '@/portal/api/types';

export const TEST_DARTS: Dart[] = [
  {
    id: 1,
    name: 'Palo Alto',
    airport_identifiers: 'PAO',
    website_url: '',
    contacts: [],
  },
  {
    id: 2,
    name: 'Watsonville',
    airport_identifiers: 'WVI',
    website_url: '',
    contacts: [],
  },
];

/** The aircraft types the default `GET /aircraft/types` handler searches. */
export const TEST_AIRCRAFT_TYPES: AircraftType[] = [
  {
    id: 1,
    make: 'Cessna',
    model: '172S',
    seats: 4,
    engines: 1,
    category: 'airplane',
    is_custom: false,
  },
  {
    id: 2,
    make: 'Cessna',
    model: '182T Skylane',
    seats: 4,
    engines: 1,
    category: 'airplane',
    is_custom: false,
  },
  {
    id: 3,
    make: 'Cirrus',
    model: 'SR22',
    seats: 4,
    engines: 1,
    category: 'airplane',
    is_custom: false,
  },
  {
    id: 4,
    make: 'Piper',
    model: 'PA-28-181 Archer',
    seats: 4,
    engines: 1,
    category: 'airplane',
    is_custom: false,
  },
];

/** An aircraft type, the Cessna 182T Skylane unless `overrides` say otherwise. */
export function makeAircraftType(overrides: Partial<AircraftType> = {}): AircraftType {
  return {
    id: 2,
    make: 'Cessna',
    model: '182T Skylane',
    seats: 4,
    engines: 1,
    category: 'airplane',
    is_custom: false,
    ...overrides,
  };
}

export const TEST_AIRCRAFT: AircraftSummary = {
  id: 7,
  n_number: 'N12345',
  make: 'Cessna',
  model: '182T Skylane',
  type: makeAircraftType(),
  category: 'airplane',
  airworthiness: 'standard',
  coverage: { excluded: false, reason: '' },
  insurance_is_current: true,
  insurance_expiration: '2027-03-01',
  insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
  insurance_verified: false,
};

/** A complete `Profile` fixture, with `overrides` merged over the defaults. */
export function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    first_name: 'Marta',
    last_name: 'Reyes',
    phone: '650-555-0101',
    phone_extension: '',
    phone_alt_extension: '',
    emergency_contact_phone_extension: '',
    phone_alt: '',
    address_line1: '1 Embarcadero',
    address_line2: '',
    city: 'San Carlos',
    state: 'CA',
    postal_code: '94070',
    county: 'San Mateo',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    ham_callsign: '',
    member_since: null,
    home_airport_identifier: 'SQL',
    secondary_airport_identifier: 'PAO',
    dart: { id: 1, name: 'Palo Alto' },
    air_care_alliance_number: '',
    pilot_certificate_type: 'private',
    certificate_number: '3141592',
    ratings: ['instrument'],
    medical_type: 'third',
    medical_expiration: '2029-05-31',
    medical_is_current: true,
    flight_review_date: null,
    total_hours: 750,
    photo_id_type: 'passport',
    verification: {
      certificate: { verified: false, verified_by: null, verified_at: null },
      medical: { verified: false, verified_by: null, verified_at: null },
      photo_id: { verified: false, verified_by: null, verified_at: null },
    },
    aircraft: [],
    flies_rented_aircraft: false,
    vol_mission_pilot: false,
    vol_ground_team: false,
    vol_exercise_training: false,
    vol_member_support: false,
    vol_fundraising: false,
    vol_social_media: false,
    vol_newsletter: false,
    ...overrides,
  };
}
