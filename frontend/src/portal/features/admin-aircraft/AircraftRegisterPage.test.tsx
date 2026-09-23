import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Aircraft } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { AircraftRegisterPage, orderingFor } from './AircraftRegisterPage';

function makeAircraft(overrides: Partial<Aircraft> = {}): Aircraft {
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
    ...overrides,
  };
}

/** Record every query string the list endpoint is asked for. */
function listReturns(results: Aircraft[], seen: URLSearchParams[], count = results.length) {
  return http.get(`${API}/aircraft`, ({ request }) => {
    seen.push(new URL(request.url).searchParams);
    return HttpResponse.json({ count, next: null, previous: null, results });
  });
}

describe('orderingFor', () => {
  it('turns a column and direction into an API ordering term', () => {
    expect(orderingFor('n_number', 'asc')).toBe('n_number');
    expect(orderingFor('insurance_expiration', 'desc')).toBe('-insurance_expiration');
  });
});

describe('AircraftRegisterPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('lists the register with its insurance state', async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      listReturns(
        [
          makeAircraft(),
          makeAircraft({
            id: 2,
            n_number: 'N33MM',
            make: 'Mooney',
            model: 'M20J',
            owner_name: 'Owen Delgado',
            owner_type: 'individual',
            insurance_is_current: false,
            insurance_expiration: '2026-01-01',
          }),
        ],
        seen,
      ),
    );

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });

    expect(await screen.findByRole('link', { name: 'N172SP' })).toHaveAttribute(
      'href',
      '/admin/aircraft/1',
    );
    const table = within(screen.getByRole('table'));
    // The state is a dot beside the date rather than a chip: the column
    // heading already says "Insurance".  The wording survives as the dot's
    // accessible name, so a screen reader still hears it.
    expect(table.getByText('Insured')).toHaveClass('visually-hidden');
    expect(table.getByText('Insurance expired')).toHaveClass('visually-hidden');
    expect(table.getByText(/Flying club/)).toBeInTheDocument();
  });

  it('sends every filter to the API', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const seen: URLSearchParams[] = [];
    server.use(listReturns([makeAircraft()], seen));

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    await screen.findByRole('link', { name: 'N172SP' });

    await user.type(screen.getByLabelText('Search'), 'cessna');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
    await user.selectOptions(screen.getByLabelText('Owner type'), 'club');
    await user.selectOptions(screen.getByLabelText('Insurance'), 'expired');
    await user.selectOptions(screen.getByLabelText('Expiring within'), '60');

    await waitFor(() => {
      const last = seen[seen.length - 1]!;
      expect(last.get('search')).toBe('cessna');
      expect(last.get('owner_type')).toBe('club');
      expect(last.get('insurance')).toBe('expired');
      expect(last.get('expiring_within')).toBe('60');
    });
  });

  it('asks the server to re-sort when a header is clicked', async () => {
    const user = userEvent.setup();
    const seen: URLSearchParams[] = [];
    server.use(listReturns([makeAircraft()], seen));

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    await screen.findByRole('link', { name: 'N172SP' });

    await user.click(screen.getByRole('button', { name: /Insurance/ }));
    await waitFor(() =>
      expect(seen[seen.length - 1]!.get('ordering')).toBe('insurance_expiration'),
    );

    await user.click(screen.getByRole('button', { name: /Insurance/ }));
    await waitFor(() =>
      expect(seen[seen.length - 1]!.get('ordering')).toBe('-insurance_expiration'),
    );
  });

  it('points the export buttons at the filtered report', async () => {
    const user = userEvent.setup();
    const seen: URLSearchParams[] = [];
    server.use(listReturns([makeAircraft()], seen));

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    await screen.findByRole('link', { name: 'N172SP' });

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      '/api/v1/admin/aircraft/export.csv?ordering=n_number',
    );

    await user.selectOptions(screen.getByLabelText('Insurance'), 'missing');

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Export PDF' })).toHaveAttribute(
        'href',
        '/api/v1/admin/aircraft/export.pdf?insurance=missing&ordering=n_number',
      ),
    );
  });

  it('pages through a register larger than one page', async () => {
    const user = userEvent.setup();
    const seen: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/aircraft`, ({ request }) => {
        const params = new URL(request.url).searchParams;
        seen.push(params);
        const page = Number(params.get('page') ?? '1');
        return HttpResponse.json({
          count: 40,
          next: page === 1 ? 'http://x/?page=2' : null,
          previous: page === 1 ? null : 'http://x/?page=1',
          results: [makeAircraft({ id: page, n_number: page === 1 ? 'N172SP' : 'N9021K' })],
        });
      }),
    );

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    expect(await screen.findByText('1–25 of 40')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Next/ }));
    expect(await screen.findByRole('link', { name: 'N9021K' })).toBeInTheDocument();
    expect(screen.getByText('26–40 of 40')).toBeInTheDocument();
  });

  it('shows an empty state when nothing matches', async () => {
    const seen: URLSearchParams[] = [];
    server.use(listReturns([], seen, 0));

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    expect(await screen.findByText(/No aircraft match these filters/)).toBeInTheDocument();
  });

  it('adds an aircraft and opens its record', async () => {
    const user = userEvent.setup();
    const seen: URLSearchParams[] = [];
    let posted: Record<string, unknown> | null = null;
    server.use(
      listReturns([], seen, 0),
      http.post(`${API}/aircraft`, async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { ...makeAircraft({ id: 42, n_number: 'N4321Q' }), pilots: [] },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    await user.click(screen.getByRole('button', { name: 'New aircraft' }));

    const form = screen.getByRole('group', { name: 'Aircraft' });
    await user.type(within(form).getByLabelText(/^N-number/), 'n4321q');
    await user.type(within(form).getByLabelText(/^Make/), 'Cirrus');
    await user.type(within(form).getByLabelText(/^Model/), 'SR22');
    await user.click(screen.getByRole('button', { name: 'Add aircraft' }));

    await waitFor(() => expect(posted).toMatchObject({ n_number: 'N4321Q', make: 'Cirrus' }));
  });

  it('surfaces a duplicate registration from the server', async () => {
    const user = userEvent.setup();
    const seen: URLSearchParams[] = [];
    server.use(
      listReturns([], seen, 0),
      http.post(`${API}/aircraft`, () =>
        HttpResponse.json(
          { n_number: ['An aircraft with this N-number is already on file.'] },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<AircraftRegisterPage />, { route: '/admin/aircraft' });
    await user.click(screen.getByRole('button', { name: 'New aircraft' }));

    const form = screen.getByRole('group', { name: 'Aircraft' });
    await user.type(within(form).getByLabelText(/^N-number/), 'n172sp');
    await user.type(within(form).getByLabelText(/^Make/), 'Cessna');
    await user.type(within(form).getByLabelText(/^Model/), '172S');
    await user.click(screen.getByRole('button', { name: 'Add aircraft' }));

    expect(await screen.findByText(/already on file/)).toBeInTheDocument();
  });
});
