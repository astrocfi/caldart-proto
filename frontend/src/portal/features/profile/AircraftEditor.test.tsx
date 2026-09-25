import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

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
    notes: '',
    created_by: MEMBER_ID,
    is_active: true,
    pilots: [],
    ...overrides,
  };
}

function renderEditor(detail: AircraftDetail) {
  server.use(http.get(`${API}/aircraft/7`, () => HttpResponse.json(detail)));
  return renderWithProviders(
    <AircraftEditor aircraftId={7} userId={MEMBER_ID} onClose={() => {}} onSaved={() => {}} />,
  );
}

describe('<AircraftEditor/>', () => {
  beforeEach(() => {
    server.use(signedInAs(makeUser({ id: MEMBER_ID })));
  });

  it('edits a record the member added themselves', async () => {
    renderEditor(makeDetail());

    expect(await screen.findByRole('button', { name: 'Save aircraft' })).toBeInTheDocument();
  });

  it('asks the member to go to an account administrator about a record somebody else added', async () => {
    renderEditor(makeDetail({ created_by: 99 }));

    expect(await screen.findByText('Someone else added this aircraft')).toBeInTheDocument();
    expect(
      screen.getByText('Ask a CalDART account administrator to correct it.'),
    ).toBeInTheDocument();
  });
});
