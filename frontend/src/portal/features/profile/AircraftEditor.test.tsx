import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { makeAircraftType } from '@test/fixtures/profile';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftDetail } from '@/portal/api/types';
import { AircraftEditor } from './AircraftEditor';

const MEMBER_ID = 42;

function makeDetail(overrides: Partial<AircraftDetail> = {}): AircraftDetail {
  return {
    id: 7,
    n_number: 'N12345',
    make: 'Cessna',
    model: '182T Skylane',
    type: makeAircraftType(),
    category: 'airplane',
    airworthiness: 'standard',
    coverage: { excluded: false, reason: '' },
    year: 2004,
    owner_type: 'individual',
    owner_name: 'Dana Ruiz',
    owner_contact: '',
    seats: 4,
    insurance_carrier: 'Avemco',
    insurance_policy_number: 'AV-1',
    insurance_liability_per_occurrence_cents: 100_000_000,
    insurance_liability_per_person_cents: 10_000_000,
    insurance_hull_cents: null,
    insurance_is_current: true,
    insurance_expiration: '2027-03-01',
    insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
    insurance_verification: { verified: false, verified_by: null, verified_at: null },
    notes: '',
    created_by: MEMBER_ID,
    updated_at: '2026-09-01T12:00:00Z',
    updated_by: null,
    is_active: true,
    pilots: [],
    ...overrides,
  };
}

function renderEditor(detail: AircraftDetail) {
  server.use(http.get(`${API}/aircraft/7`, () => HttpResponse.json(detail)));
  return renderWithProviders(
    <AircraftEditor aircraftId={7} onClose={() => {}} onSaved={() => {}} />,
  );
}

describe('<AircraftEditor/>', () => {
  beforeEach(() => {
    server.use(signedInAs(makeUser({ id: MEMBER_ID })));
  });

  it('edits the record in the shared aircraft form', async () => {
    renderEditor(makeDetail());

    expect(await screen.findByRole('button', { name: 'Save changes' })).toBeInTheDocument();
  });

  it('shows liability limits nobody recorded as blank boxes, not as 0', async () => {
    renderEditor(
      makeDetail({
        insurance_liability_per_occurrence_cents: 0,
        insurance_liability_per_person_cents: 0,
      }),
    );

    await screen.findByRole('button', { name: 'Save changes' });
    expect(screen.getByLabelText(/^Liability per occurrence/)).toHaveValue('');
    expect(screen.getByLabelText(/^Liability per person/)).toHaveValue('');
  });
});
