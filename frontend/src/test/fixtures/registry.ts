/** Test data for the FAA registry: a registration, an import, and the registry's state.  Not shipped. */
import type { Registration, RegistryImport, RegistryStatus } from '@/portal/api/types';
import { makeAircraftType } from './profile';

/** A valid registration of a Cessna 172S, `overrides` merged over. */
export function makeRegistration(overrides: Partial<Registration> = {}): Registration {
  return {
    n_number: 'N739TA',
    type: makeAircraftType({ id: 1, model: '172S', seats: 4 }),
    year: 2004,
    registrant_name: 'PALO ALTO FLYING CLUB',
    registrant_type: 'corporation',
    status: 'valid',
    certificate_issued_on: '2019-05-02',
    expires_on: '2026-05-31',
    airworthiness: 'standard',
    imported_at: '2026-09-20T11:30:00Z',
    ...overrides,
  };
}

/** A finished, successful import, `overrides` merged over. */
export function makeRegistryImport(overrides: Partial<RegistryImport> = {}): RegistryImport {
  return {
    started_at: '2026-09-20T11:28:00Z',
    finished_at: '2026-09-20T11:30:00Z',
    ok: true,
    error: '',
    types_written: 312,
    registrations_written: 204,
    types_folded: 0,
    source: 'https://registry.faa.gov/database/ReleasableAircraft.zip',
    ...overrides,
  };
}

/** The registry's state after one successful import, `overrides` merged over. */
export function makeRegistryStatus(overrides: Partial<RegistryStatus> = {}): RegistryStatus {
  const last = makeRegistryImport();
  return { as_of: last.finished_at, running: false, last, ...overrides };
}
