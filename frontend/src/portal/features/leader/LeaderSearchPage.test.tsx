import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API, makeLeaderStatus } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { LeaderSearchResult } from '@/portal/api/types';
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
  go_no_go: { membership: true, medical: true, verified: true },
};

const STATUS = makeLeaderStatus({
  medical: { ...makeLeaderStatus().medical, expiration: '2027-12-01' },
  aircraft: [],
});

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

  it('searches by name and lists the matches', async () => {
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
    expect(screen.getByText('Owen Delgado')).toBeInTheDocument();
    expect(queries).toEqual(['reyes']);
  });

  it('shows the name, the DART, the email, and the verdict', async () => {
    const user = setupUser();
    server.use(searchReturns([MARTA]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    const marta = await screen.findByRole('button', { name: /Marta Reyes/ });
    expect(marta).toHaveTextContent(
      /^Marta ReyesPalo Alto DART · marta@example\.orgCleared to flyGO$/,
    );
  });

  it('counts one match as 1 person found', async () => {
    const user = setupUser();
    server.use(searchReturns([MARTA]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    expect(await screen.findByText('1 person found')).toBeInTheDocument();
  });

  it('counts several matches as people found', async () => {
    const user = setupUser();
    server.use(searchReturns([MARTA, { ...MARTA, user_id: 8, email: 'marta.r@example.org' }]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    expect(await screen.findByText('2 people found')).toBeInTheDocument();
  });

  it('tells two people of the same name apart by their DART and email', async () => {
    const user = setupUser();
    const namesake = { ...MARTA, user_id: 8, dart: null, email: 'marta.r@example.org' };
    server.use(searchReturns([MARTA, namesake]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    const rows = await screen.findAllByRole('button', { name: /Marta Reyes/ });
    expect(rows.map((row) => row.textContent)).toEqual([
      'Marta ReyesPalo Alto DART · marta@example.orgCleared to flyGO',
      'Marta ReyesNo DART · marta.r@example.orgCleared to flyGO',
    ]);
  });

  it('leaves the membership state to the card, so the row says go or no-go alone', async () => {
    const user = setupUser();
    server.use(searchReturns([{ ...MARTA, membership_status: 'expired' }]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    await screen.findByRole('button', { name: /Marta Reyes/ });
    expect(screen.queryByText('Member expired')).not.toBeInTheDocument();
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
          go_no_go: { membership: false, medical: false, verified: true },
        },
      ]),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'a');

    const marta = await screen.findByRole('button', { name: /Marta Reyes/ });
    expect(within(marta).getByText('GO')).toBeInTheDocument();
    const owen = screen.getByRole('button', { name: /Owen Delgado/ });
    expect(within(owen).getByText('NO-GO')).toBeInTheDocument();
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

    await user.click(screen.getByRole('link', { name: 'Back to search' }));
    expect(screen.getByLabelText(/Name, email, phone, or N-number/i)).toBeInTheDocument();
  });

  it('moves the focus to the card the leader picks', async () => {
    const user = setupUser();
    server.use(
      searchReturns([MARTA]),
      http.get(`${API}/leader/members/7/status`, () => HttpResponse.json(STATUS)),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');
    await user.click(await screen.findByRole('button', { name: /Marta Reyes/ }));

    expect(document.activeElement).toContainElement(
      await screen.findByRole('heading', { name: 'Marta Reyes' }),
    );
  });

  it('moves the focus back to the search box from the card', async () => {
    const user = setupUser();
    server.use(
      searchReturns([MARTA]),
      http.get(`${API}/leader/members/7/status`, () => HttpResponse.json(STATUS)),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=7' });
    await screen.findByText('GO');
    await user.click(screen.getByRole('link', { name: 'Back to search' }));

    expect(screen.getByLabelText(/Name, email, phone, or N-number/i)).toHaveFocus();
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
        HttpResponse.json(
          { detail: "That isn't here. It may have been deleted." },
          { status: 404 },
        ),
      ),
    );
    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=7' });
    expect(await screen.findByText('We could not find that person')).toBeInTheDocument();
    expect(screen.getByText('Their account may have been deleted.')).toBeInTheDocument();
  });

  it('offers the aircraft check when an N-number matches no member', async () => {
    const user = setupUser();
    server.use(searchReturns([]));

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'n-172sp');

    expect(await screen.findByText(/Nobody matches that/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Check N172SP/ })).toHaveAttribute(
      'href',
      '/leader/aircraft?aircraft=N172SP',
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

  it('marks a current member whose items are not all verified NO-GO', async () => {
    const user = setupUser();
    server.use(
      searchReturns([{ ...MARTA, go_no_go: { membership: true, medical: true, verified: false } }]),
    );

    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    await search(user, 'reyes');

    const marta = await screen.findByRole('button', { name: /Marta Reyes/ });
    expect(marta).toHaveTextContent(/^Marta Reyes.*Not cleared to flyNO-GO$/);
  });

  it('says what the verification report holds beside its downloads', () => {
    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    const group = screen.getByRole('group', { name: 'Everything nobody has checked yet:' });
    expect(within(group).getAllByRole('link')).toHaveLength(2);
  });

  it('offers the verification report for download above the search', () => {
    renderWithProviders(<LeaderSearchPage />, { route: '/leader' });
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      '/api/v1/reports/verification/export.csv',
    );
    expect(screen.getByRole('link', { name: 'Export PDF' })).toHaveAttribute(
      'href',
      '/api/v1/reports/verification/export.pdf',
    );
  });

  it('leaves the report off the screen while a card is open', async () => {
    server.use(http.get(`${API}/leader/members/7/status`, () => HttpResponse.json(STATUS)));
    renderWithProviders(<LeaderSearchPage />, { route: '/leader?member=7' });
    expect(await screen.findByText('GO')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Export CSV' })).not.toBeInTheDocument();
  });
});
