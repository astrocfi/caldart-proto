/** Test data for the profile, join and dashboard suites.  Not shipped. */
import type { AircraftSummary, Dart, Profile } from '../../api/types';

export const TEST_DARTS: Dart[] = [
  { id: 1, name: 'Palo Alto', airport_identifier: 'PAO', city: 'Palo Alto' },
  { id: 2, name: 'Watsonville', airport_identifier: 'WVI', city: 'Watsonville' },
];

export const TEST_AIRCRAFT: AircraftSummary = {
  id: 7,
  n_number: 'N12345',
  make: 'Cessna',
  model: '182T Skylane',
  insurance_is_current: true,
  insurance_expiration: '2027-03-01',
  insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
};

/** A complete `Profile` fixture, with `overrides` merged over the defaults. */
export function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    phone: '650-555-0101',
    phone_alt: '',
    address_line1: '1 Embarcadero',
    address_line2: '',
    city: 'San Carlos',
    state: 'CA',
    postal_code: '94070',
    county: 'San Mateo',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    home_airport_identifier: 'SQL',
    home_airport_city: 'San Carlos',
    dart: { id: 1, name: 'Palo Alto' },
    air_care_alliance_number: '',
    pilot_certificate_type: 'private',
    certificate_number: '3141592',
    ifr_rated: 'yes',
    ratings: ['instrument'],
    medical_type: 'third',
    medical_expiration: '2029-05-31',
    medical_is_current: true,
    flight_review_date: null,
    total_hours: 750,
    aircraft: [],
    vol_ground_team: false,
    vol_exercise_training: false,
    vol_member_support: false,
    vol_fundraising: false,
    vol_social_media: false,
    vol_newsletter: false,
    ...overrides,
  };
}
