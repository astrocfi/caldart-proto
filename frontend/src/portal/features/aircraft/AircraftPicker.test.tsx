import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Aircraft } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { AircraftPicker } from './AircraftPicker';

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Type into the search box, then settle the debounce with the fake clock. */
async function search(user: ReturnType<typeof setupUser>, label: RegExp, text: string) {
  await user.type(screen.getByLabelText(label), text);
  await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
}

function makeAircraft(overrides: Partial<Aircraft> = {}): Aircraft {
  return {
    id: 1,
    n_number: 'N172SP',
    make: 'Cessna',
    model: '172S Skyhawk',
    insurance_is_current: true,
    insurance_expiration: '2027-03-01',
    insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
    updated_at: '2026-09-01T12:00:00Z',
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

/** Lookup 404s, search returns `results`. */
function searchOnly(results: Aircraft[]) {
  return [
    http.get(`${API}/aircraft/lookup`, () =>
      HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
    ),
    http.get(`${API}/aircraft`, () =>
      HttpResponse.json({ count: results.length, next: null, previous: null, results }),
    ),
  ];
}

describe('AircraftPicker', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('looks the registration up first and lists the exact match', async () => {
    const user = setupUser();
    const aircraft = makeAircraft();
    const seen: string[] = [];
    server.use(
      http.get(`${API}/aircraft/lookup`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('n_number') ?? '');
        return HttpResponse.json({ ...aircraft, pilots: [] });
      }),
    );

    const handleSelect = vi.fn();
    renderWithProviders(<AircraftPicker onSelect={handleSelect} />);

    await search(user, /Search the aircraft register/i, 'n-172sp');

    expect(await screen.findByText('N172SP')).toBeInTheDocument();
    expect(seen).toEqual(['n-172sp']);
    expect(screen.getByText('Insured')).toBeInTheDocument();
  });

  it('falls back to a search when the registration is unknown', async () => {
    const user = setupUser();
    let searchTerm: string | null = null;
    server.use(
      http.get(`${API}/aircraft/lookup`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
      http.get(`${API}/aircraft`, ({ request }) => {
        searchTerm = new URL(request.url).searchParams.get('search');
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeAircraft({ id: 7, n_number: 'N9021K', make: 'Piper', model: 'Archer' })],
        });
      }),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'archer');

    expect(await screen.findByText('N9021K')).toBeInTheDocument();
    expect(searchTerm).toBe('archer');
  });

  it('hands the chosen aircraft to onSelect', async () => {
    const user = setupUser();
    const aircraft = makeAircraft();
    server.use(...searchOnly([aircraft]));

    const handleSelect = vi.fn();
    renderWithProviders(<AircraftPicker onSelect={handleSelect} />);
    await search(user, /Search the aircraft register/i, 'cessna');

    await user.click(await screen.findByRole('button', { name: /N172SP/ }));
    expect(handleSelect).toHaveBeenCalledWith(aircraft);
  });

  it('leaves out aircraft the member has already attached', async () => {
    const user = setupUser();
    server.use(
      ...searchOnly([
        makeAircraft({ id: 1, n_number: 'N172SP' }),
        makeAircraft({ id: 2, n_number: 'N9021K' }),
      ]),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} excludeIds={[1]} />);
    await search(user, /Search the aircraft register/i, 'cessna');

    expect(await screen.findByText('N9021K')).toBeInTheDocument();
    const list = screen.getByRole('list');
    expect(within(list).queryByText('N172SP')).not.toBeInTheDocument();
    expect(screen.getByText('N172SP is already on your list.')).toBeInTheDocument();
  });

  it('names two attached aircraft with "and" between them', async () => {
    const user = setupUser();
    server.use(
      ...searchOnly([
        makeAircraft({ id: 1, n_number: 'N172SP' }),
        makeAircraft({ id: 2, n_number: 'N9021K' }),
      ]),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} excludeIds={[1, 2]} />);
    await search(user, /Search the aircraft register/i, 'cessna');

    expect(
      await screen.findByText('N172SP and N9021K are already on your list.'),
    ).toBeInTheDocument();
  });

  it('separates three attached aircraft with commas and a final "and"', async () => {
    const user = setupUser();
    server.use(
      ...searchOnly([
        makeAircraft({ id: 1, n_number: 'N172SP' }),
        makeAircraft({ id: 2, n_number: 'N9021K' }),
        makeAircraft({ id: 3, n_number: 'N4321Q' }),
      ]),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} excludeIds={[1, 2, 3]} />);
    await search(user, /Search the aircraft register/i, 'cessna');

    expect(
      await screen.findByText('N172SP, N9021K, and N4321Q are already on your list.'),
    ).toBeInTheDocument();
  });

  it('leaves out-of-service aircraft out of the fuzzy search', async () => {
    const user = setupUser();
    let params: URLSearchParams | null = null;
    server.use(
      http.get(`${API}/aircraft/lookup`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
      http.get(`${API}/aircraft`, ({ request }) => {
        params = new URL(request.url).searchParams;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'cessna');
    await screen.findByText(/No aircraft matches that/i);

    expect(params!.get('is_active')).toBe('true');
  });

  it('flags an exact match that is out of service rather than hiding it', async () => {
    const user = setupUser();
    server.use(
      http.get(`${API}/aircraft/lookup`, () =>
        HttpResponse.json({ ...makeAircraft({ is_active: false }), pilots: [] }),
      ),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n172sp');

    expect(await screen.findByText('N172SP')).toBeInTheDocument();
    expect(screen.getByText('Out of service')).toBeInTheDocument();
  });

  it('does not offer to create one the member has already attached', async () => {
    const user = setupUser();
    server.use(...searchOnly([makeAircraft({ id: 1, n_number: 'N172SP' })]));

    renderWithProviders(<AircraftPicker onSelect={() => {}} excludeIds={[1]} />);
    await search(user, /Search the aircraft register/i, 'n172sp');

    expect(await screen.findByText('N172SP is already on your list.')).toBeInTheDocument();
    expect(screen.queryByText(/No aircraft matches that/i)).not.toBeInTheDocument();
  });

  it('offers to create an aircraft when nothing matches', async () => {
    const user = setupUser();
    server.use(...searchOnly([]));

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n4321q');

    expect(await screen.findByText(/No aircraft matches that/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Add a new aircraft/i }));

    // The registration the member typed is carried into the form, normalized.
    expect(screen.getByLabelText(/^N-number/)).toHaveValue('N4321Q');
  });

  it('offers exactly one way to add an aircraft when nothing matches', async () => {
    const user = setupUser();
    server.use(...searchOnly([]));

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n4321q');

    const empty = (await screen.findByText(/No aircraft matches that/i)).closest('.empty-state');
    expect(screen.getAllByRole('button', { name: /Add a new aircraft/i })).toHaveLength(1);
    expect(empty).not.toBeNull();
    expect(within(empty as HTMLElement).queryByRole('button')).not.toBeInTheDocument();
  });

  it('points at the button below rather than repeating it in the empty state', async () => {
    const user = setupUser();
    server.use(...searchOnly([]));

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n4321q');

    expect(
      await screen.findByText('If the plane is not in the register yet, add it below.'),
    ).toBeInTheDocument();
  });

  it('keeps the add button below the results the search found', async () => {
    const user = setupUser();
    server.use(...searchOnly([makeAircraft()]));

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'cessna');

    const list = await screen.findByRole('list');
    const add = screen.getByRole('button', { name: /Add a new aircraft/i });
    expect(list.compareDocumentPosition(add)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it('says what a result does when the search found some', async () => {
    const user = setupUser();
    server.use(...searchOnly([makeAircraft()]));

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'cessna');

    expect(
      await screen.findByText('Click on an aircraft to add it to your list.'),
    ).toBeInTheDocument();
  });

  it('says nothing about clicking a result before a search has found one', () => {
    renderWithProviders(<AircraftPicker onSelect={() => {}} />);

    expect(screen.queryByText(/Click on an aircraft/i)).not.toBeInTheDocument();
  });

  it('creates the aircraft and selects it', async () => {
    const user = setupUser();
    const created = makeAircraft({ id: 42, n_number: 'N4321Q', make: 'Cirrus', model: 'SR22' });
    let posted: Record<string, unknown> | null = null;
    server.use(
      ...searchOnly([]),
      http.post(`${API}/aircraft`, async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...created, pilots: [] }, { status: 201 });
      }),
    );

    const handleSelect = vi.fn();
    renderWithProviders(<AircraftPicker onSelect={handleSelect} />);
    await search(user, /Search the aircraft register/i, 'n4321q');
    await user.click(await screen.findByRole('button', { name: /Add a new aircraft/i }));

    await user.type(screen.getByLabelText(/^Make/), 'Cirrus');
    await user.type(screen.getByLabelText(/^Model/), 'SR22');
    await user.click(screen.getByRole('button', { name: /^Add aircraft$/ }));

    await waitFor(() =>
      expect(handleSelect).toHaveBeenCalledWith(expect.objectContaining(created)),
    );
    expect(posted).toMatchObject({ n_number: 'N4321Q', make: 'Cirrus', model: 'SR22' });
  });

  it('will not submit without a make and model', async () => {
    const user = setupUser();
    const post = vi.fn();
    server.use(
      ...searchOnly([]),
      http.post(`${API}/aircraft`, () => {
        post();
        return HttpResponse.json({}, { status: 201 });
      }),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n4321q');
    await user.click(await screen.findByRole('button', { name: /Add a new aircraft/i }));
    await user.click(screen.getByRole('button', { name: /^Add aircraft$/ }));

    expect(await screen.findByText(/Enter the make/i)).toBeInTheDocument();
    expect(screen.getByText(/Enter the model/i)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it('shows the server’s field errors, such as a duplicate registration', async () => {
    const user = setupUser();
    server.use(
      ...searchOnly([]),
      http.post(`${API}/aircraft`, () =>
        HttpResponse.json(
          { n_number: ['An aircraft with this N-number is already on file.'] },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n172sp');
    await user.click(await screen.findByRole('button', { name: /Add a new aircraft/i }));
    await user.type(screen.getByLabelText(/^Make/), 'Cessna');
    await user.type(screen.getByLabelText(/^Model/), '172S');
    await user.click(screen.getByRole('button', { name: /^Add aircraft$/ }));

    expect(await screen.findByText(/already on file/i)).toBeInTheDocument();
  });

  it('asks the server once per settled search term', async () => {
    const user = setupUser();
    let lookups = 0;
    server.use(
      http.get(`${API}/aircraft/lookup`, () => {
        lookups += 1;
        return HttpResponse.json({ detail: 'Not found.' }, { status: 404 });
      }),
      http.get(`${API}/aircraft`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );

    renderWithProviders(<AircraftPicker onSelect={() => {}} />);
    await search(user, /Search the aircraft register/i, 'n172sp');
    await screen.findByText(/No aircraft matches that/i);

    expect(lookups).toBe(1);
  });
});
