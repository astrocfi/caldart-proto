import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { LeaderSearchResult, LeaderStatus } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { LeaderSearchPage } from './LeaderSearchPage';

const SEARCH_LABEL = /Name, email, phone, or N-number/i;

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Type into the search box, then settle the debounce with the fake clock. */
async function search(user: ReturnType<typeof setupUser>, text: string) {
  await user.type(screen.getByLabelText(SEARCH_LABEL), text);
  await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
}

const MARTA: LeaderSearchResult = {
  user_id: 7,
  name: 'Marta Reyes',
  email: 'marta@example.org',
  dart: 'Palo Alto',
  membership_status: 'current',
  medical: { type: 'third', expiration: '2027-12-01', is_current: true },
  go_no_go: { membership: true, medical: true },
};

const STATUS: LeaderStatus = {
  name: 'Marta Reyes',
  email: 'marta@example.org',
  phone: '650-555-0100',
  dart: 'Palo Alto',
  membership: { status: 'current', expires_on: '2027-06-30', plan: 'Annual' },
  certificate: { type: 'private', number: '3181234', ifr_rated: 'yes', ratings: ['instrument'] },
  medical: { type: 'third', expiration: '2027-12-01', is_current: true },
  aircraft: [],
  go_no_go: { membership: true, medical: true },
};

function searchReturns(results: LeaderSearchResult[], onQuery?: (q: string) => void) {
  return http.get(`${API}/leader/search`, ({ request }) => {
    onQuery?.(new URL(request.url).searchParams.get('q') ?? '');
    return HttpResponse.json(results);
  });
}

describe('LeaderSearchPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('searches by name and lists the matches with their membership state', async () => {
    const user = setupUser();
    const queries: string[] = [];
    server.use(
      searchReturns(
        [MARTA, { ...MARTA, user_id: 8, name: 'Owen Delgado', membership_status: 'expired' }],
        (q) => queries.push(q),
      ),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    expect(screen.getByText('Member current')).toBeInTheDocument();
    expect(screen.getByText('Member expired')).toBeInTheDocument();
    expect(queries).toEqual(['reyes']);
  });

  it('answers go or no-go on every row, so the list needs no click', async () => {
    const user = setupUser();
    server.use(
      searchReturns([
        MARTA,
        {
          ...MARTA,
          user_id: 8,
          name: 'Owen Delgado',
          membership_status: 'expired',
          medical: { type: 'third', expiration: '2026-01-31', is_current: false },
          go_no_go: { membership: false, medical: false },
        },
      ]),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'a');

    expect(await screen.findByText('GO')).toBeInTheDocument();
    expect(screen.getByText('NO-GO')).toBeInTheDocument();
  });

  it('prints the medical in words beside the verdict', async () => {
    const user = setupUser();
    server.use(searchReturns([MARTA]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    expect(await screen.findByText('Class 3 medical to 2027/12/01')).toBeInTheDocument();
  });

  it('says when a medical has run out', async () => {
    const user = setupUser();
    server.use(
      searchReturns([
        {
          ...MARTA,
          medical: { type: 'first', expiration: '2026-01-31', is_current: false },
          go_no_go: { membership: true, medical: false },
        },
      ]),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    expect(await screen.findByText('Medical expired 2026/01/31')).toBeInTheDocument();
  });

  it('says when there is no medical at all', async () => {
    const user = setupUser();
    server.use(
      searchReturns([
        {
          ...MARTA,
          medical: { type: 'none', expiration: null, is_current: false },
          go_no_go: { membership: true, medical: false },
        },
      ]),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    expect(await screen.findByText('No medical on file')).toBeInTheDocument();
  });

  it('searches by N-number too', async () => {
    const user = setupUser();
    const queries: string[] = [];
    server.use(searchReturns([MARTA], (q) => queries.push(q)));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'N172SP');

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    expect(queries).toEqual(['N172SP']);
  });

  it('opens the status card for the member the leader picks', async () => {
    const user = setupUser();
    server.use(
      searchReturns([MARTA]),
      http.get(`${API}/leader/members/7/status`, () => HttpResponse.json(STATUS)),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');
    await user.click(await screen.findByRole('button', { name: /Marta Reyes/ }));

    expect(await screen.findByText('GO')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Marta Reyes' })).toBeInTheDocument();
  });

  it('goes back to the search from the card', async () => {
    const user = setupUser();
    server.use(
      searchReturns([MARTA]),
      http.get(`${API}/leader/members/7/status`, () => HttpResponse.json(STATUS)),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=7' });
    expect(await screen.findByText('GO')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Back to search/ }));
    expect(screen.getByLabelText(/Name, email, phone, or N-number/i)).toBeInTheDocument();
  });

  it('reads the member out of the query string, so a card can be linked', async () => {
    server.use(http.get(`${API}/leader/members/7/status`, () => HttpResponse.json(STATUS)));
    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=7' });
    expect(await screen.findByText('GO')).toBeInTheDocument();
  });

  it('ignores a member id that is not a record id', async () => {
    let asked = false;
    server.use(
      searchReturns([]),
      http.get(`${API}/leader/members/:id/status`, () => {
        asked = true;
        return HttpResponse.json(STATUS);
      }),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=abc' });
    expect(await screen.findByLabelText(/Name, email, phone, or N-number/i)).toBeInTheDocument();
    expect(asked).toBe(false);
  });

  it('explains a 404 rather than showing an empty card', async () => {
    server.use(
      http.get(`${API}/leader/members/7/status`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=7' });
    expect(await screen.findByText(/could not be loaded/i)).toBeInTheDocument();
  });

  it('offers the aircraft check when an N-number matches no member', async () => {
    const user = setupUser();
    server.use(searchReturns([]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'n-172sp');

    expect(await screen.findByText(/Nobody matches that/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Check N172SP/ })).toHaveAttribute(
      'href',
      '/leader/aircraft?n_number=N172SP',
    );
  });

  it('suggests another search when a name matches nobody', async () => {
    const user = setupUser();
    server.use(searchReturns([]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'nobody');

    expect(await screen.findByText(/Try a surname/i)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Check/ })).not.toBeInTheDocument();
  });
});
