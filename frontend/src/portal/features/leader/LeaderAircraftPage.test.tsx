import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type { AircraftDetail } from '../aircraft/api';
import { LeaderAircraftPage } from './LeaderAircraftPage';

function makeDetail(overrides: Partial<AircraftDetail> = {}): AircraftDetail {
  return {
    id: 1,
    n_number: 'N172SP',
    make: 'Cessna',
    model: '172S Skyhawk',
    insurance_is_current: true,
    insurance_expiration: '2027-03-01',
    insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
    year: 2008,
    owner_type: 'club',
    owner_name: 'Palo Alto Flying Club',
    owner_contact: 'ops@example.org',
    seats: 4,
    insurance_carrier: 'Avemco',
    insurance_policy_number: 'AV-00012345',
    insurance_liability_per_occurrence_cents: 100_000_000,
    insurance_liability_per_person_cents: 10_000_000,
    insurance_hull_cents: 14_500_000,
    notes: '',
    created_by: null,
    is_active: true,
    pilots: [
      {
        user_id: 7,
        name: 'Marta Reyes',
        email: 'marta@example.org',
        membership_status: 'current',
        medical_is_current: true,
      },
    ],
    ...overrides,
  };
}

describe('LeaderAircraftPage', () => {
  it('checks the registration typed into the box', async () => {
    const user = userEvent.setup();
    const asked: string[] = [];
    server.use(
      http.get(`${API}/leader/aircraft`, ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('n_number') ?? '');
        return HttpResponse.json(makeDetail());
      }),
    );

    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft' });
    await user.type(screen.getByLabelText(/^N-number/), 'n-172sp');
    await user.click(screen.getByRole('button', { name: /Check aircraft/ }));

    expect(await screen.findByText('INSURED')).toBeInTheDocument();
    // Normalized before it ever reaches the server.
    expect(asked).toEqual(['N172SP']);
  });

  it('reads the registration from the query string', async () => {
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeDetail())));
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?n_number=N172SP' });

    expect(await screen.findByText('INSURED')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'N172SP' })).toBeInTheDocument();
    expect(screen.getByLabelText(/^N-number/)).toHaveValue('N172SP');
  });

  it('says NOT INSURED when the policy has run out', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeDetail({ insurance_is_current: false, insurance_expiration: '2026-01-01' }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?n_number=N172SP' });

    expect(await screen.findByText('NOT INSURED')).toBeInTheDocument();
    expect(screen.getByText('Cover has expired')).toBeInTheDocument();
  });

  it('says NOT INSURED when there is no policy at all', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(makeDetail({ insurance_is_current: false, insurance_expiration: null })),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?n_number=N172SP' });

    expect(await screen.findByText('NOT INSURED')).toBeInTheDocument();
    expect(screen.getByText('No policy on file')).toBeInTheDocument();
  });

  it('lists the members who fly it with their own currency', async () => {
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeDetail())));
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?n_number=N172SP' });

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    expect(screen.getByText('Member current')).toBeInTheDocument();
    expect(screen.getByText('Medical current')).toBeInTheDocument();
  });

  it('shows the liability limits the leader has to check', async () => {
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeDetail())));
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?n_number=N172SP' });

    expect(await screen.findByText(/\$1,000,000/)).toBeInTheDocument();
    expect(screen.getByText(/\$100,000/)).toBeInTheDocument();
  });

  it('explains an unknown registration', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?n_number=N0000X' });

    expect(await screen.findByText(/N0000X is not in the register/)).toBeInTheDocument();
  });

  it('asks nothing until a registration is given', () => {
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft' });
    expect(screen.getByRole('button', { name: /Check aircraft/ })).toBeInTheDocument();
    expect(screen.queryByText(/INSURED/)).not.toBeInTheDocument();
  });
});
