import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { Route, Routes } from 'react-router-dom';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftDetail } from '@/portal/api/types';
import { AircraftRecordPage } from './AircraftRecordPage';

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
        medical_is_current: false,
      },
    ],
    ...overrides,
  };
}

/** The record page reads `:id`, so it needs a matching route around it. */
function renderRecord(route = '/admin/aircraft/1') {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/aircraft" element={<p>register</p>} />
      <Route path="/admin/aircraft/:id" element={<AircraftRecordPage />} />
    </Routes>,
    { route },
  );
}

describe('AircraftRecordPage', () => {
  it('fills the form from the record', async () => {
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())));
    renderRecord();

    expect(await screen.findByRole('heading', { name: 'N172SP' })).toBeInTheDocument();
    const form = screen.getByRole('group', { name: 'Aircraft' });
    expect(within(form).getByLabelText(/^N-number/)).toHaveValue('N172SP');
    expect(within(form).getByLabelText(/^Make/)).toHaveValue('Cessna');
    expect(within(form).getByLabelText(/^Year/)).toHaveValue('2008');

    const insurance = screen.getByRole('group', { name: 'Insurance' });
    expect(within(insurance).getByLabelText(/Liability per occurrence/)).toHaveValue('1,000,000');
    expect(within(insurance).getByLabelText(/Insurance expires/)).toHaveValue('2027-03-01');
  });

  it('saves an edit as integer cents', async () => {
    const user = userEvent.setup();
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())),
      http.patch(`${API}/aircraft/1`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...makeDetail(), insurance_carrier: 'USAIG' });
      }),
    );

    renderRecord();
    const insurance = await screen.findByRole('group', { name: 'Insurance' });
    const carrier = within(insurance).getByLabelText('Carrier');
    await user.clear(carrier);
    await user.type(carrier, 'USAIG');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(patched).toMatchObject({
        insurance_carrier: 'USAIG',
        insurance_liability_per_occurrence_cents: 100_000_000,
        insurance_hull_cents: 14_500_000,
      }),
    );
    expect(await screen.findByText(/N172SP saved/)).toBeInTheDocument();
  });

  it('reports a validation error from the server', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())),
      http.patch(`${API}/aircraft/1`, () =>
        HttpResponse.json(
          { insurance_liability_per_person_cents: ['Enter an amount of $0 or more.'] },
          { status: 400 },
        ),
      ),
    );

    renderRecord();
    await screen.findByRole('heading', { name: 'N172SP' });
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText(/\$0 or more/)).toBeInTheDocument();
  });

  it('will not save an empty make', async () => {
    const user = userEvent.setup();
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())));

    renderRecord();
    const form = await screen.findByRole('group', { name: 'Aircraft' });
    await user.clear(within(form).getByLabelText(/^Make/));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText(/Enter the make/)).toBeInTheDocument();
  });

  it('lists the pilots with their membership and medical currency', async () => {
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())));
    renderRecord();

    expect(await screen.findByRole('link', { name: 'Marta Reyes' })).toHaveAttribute(
      'href',
      '/admin/members/7',
    );
    expect(screen.getByText('Member current')).toBeInTheDocument();
    expect(screen.getByText('Medical not current')).toBeInTheDocument();
  });

  it('says so when nobody flies it', async () => {
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail({ pilots: [] }))));
    renderRecord();
    expect(await screen.findByText(/No member lists this aircraft/)).toBeInTheDocument();
  });

  it('asks for confirmation before deleting, and then deletes', async () => {
    const user = userEvent.setup();
    let deleted = false;
    server.use(
      http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())),
      http.delete(`${API}/aircraft/1`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderRecord();
    await user.click(await screen.findByRole('button', { name: 'Delete this aircraft' }));
    expect(screen.getByText(/Delete N172SP permanently/)).toBeInTheDocument();
    expect(deleted).toBe(false);

    await user.click(screen.getByRole('button', { name: /Yes, delete it/ }));
    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByText('register')).toBeInTheDocument();
  });

  it('leads the delete with the trashcan the rest of the portal uses', async () => {
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())));

    renderRecord();

    const remove = await screen.findByRole('button', { name: 'Delete this aircraft' });
    expect(remove.querySelector('svg')).toBeInTheDocument();
  });

  it('can be talked out of deleting', async () => {
    const user = userEvent.setup();
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail())));

    renderRecord();
    await user.click(await screen.findByRole('button', { name: 'Delete this aircraft' }));
    await user.click(screen.getByRole('button', { name: 'Keep it' }));

    expect(screen.queryByText(/permanently/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete this aircraft' })).toBeInTheDocument();
  });

  it('does not sit on "Loading…" for an id that is not a record id', async () => {
    let asked = false;
    server.use(
      http.get(`${API}/aircraft/:id`, () => {
        asked = true;
        return HttpResponse.json(makeDetail());
      }),
    );

    renderRecord('/admin/aircraft/abc');
    expect(await screen.findByText('No such aircraft')).toBeInTheDocument();
    expect(asked).toBe(false);
  });

  it('renders a record the server sent without a pilot list', async () => {
    const { pilots: _pilots, ...withoutPilots } = makeDetail();
    server.use(http.get(`${API}/aircraft/1`, () => HttpResponse.json(withoutPilots)));

    renderRecord();
    expect(await screen.findByRole('heading', { name: 'N172SP' })).toBeInTheDocument();
    expect(screen.getByText(/No member lists this aircraft/)).toBeInTheDocument();
  });

  it('flags an airframe that is out of service', async () => {
    server.use(
      http.get(`${API}/aircraft/1`, () => HttpResponse.json(makeDetail({ is_active: false }))),
    );

    renderRecord();
    expect(await screen.findByText('Out of service')).toBeInTheDocument();
  });

  it('explains a record that is not there', async () => {
    server.use(
      http.get(`${API}/aircraft/1`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderRecord();
    expect(await screen.findByText('No such aircraft')).toBeInTheDocument();
  });
});
