import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  API,
  NOT_VERIFIED,
  emptyVerificationCalls,
  makeUser,
  makeVerifiedAircraft,
  signedInAs,
  verificationHandlers,
} from '@test/handlers';
import { renderRoutes, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AircraftDetail } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { LeaderAircraftPage } from './LeaderAircraftPage';

const SEARCH_LABEL = /^Search by N-number/;

/** The day the search tests run on, so the list's GO/NO-GO never follows the wall clock. */
const TODAY = new Date('2026-09-24T12:00:00Z');

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Type into the search box, then settle the debounce with the fake clock. */
async function search(user: ReturnType<typeof setupUser>, text: string) {
  await user.type(screen.getByLabelText(SEARCH_LABEL), text);
  await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
}

/** The register's search: no exact registration, and `matches` for the fuzzy search. */
function registerFinds(matches: AircraftDetail[], onSearch?: (term: string) => void) {
  return [
    http.get(`${API}/aircraft/lookup`, () =>
      HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
    ),
    http.get(`${API}/aircraft`, ({ request }) => {
      onSearch?.(new URL(request.url).searchParams.get('search') ?? '');
      return HttpResponse.json({
        count: matches.length,
        next: null,
        previous: null,
        results: matches,
      });
    }),
  ];
}

/** Mount the page on its own route, so a test can read the query string it writes. */
function renderPage(route = '/leader/aircraft') {
  return renderRoutes([{ path: '/leader/aircraft', element: <LeaderAircraftPage /> }], { route });
}

describe('LeaderAircraftPage search', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(TODAY);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('searches the register as the leader types', async () => {
    const user = setupUser();
    const asked: string[] = [];
    server.use(...registerFinds([makeVerifiedAircraft()], (term) => asked.push(term)));

    renderPage();
    await search(user, 'cessna');

    expect(await screen.findByRole('button', { name: /N172SP/ })).toBeInTheDocument();
    expect(asked).toEqual(['cessna']);
  });

  it('prints the N-number, the make and model, and the insurance verdict on one row', async () => {
    const user = setupUser();
    server.use(...registerFinds([makeVerifiedAircraft()]));

    renderPage();
    await search(user, 'cessna');

    const row = await screen.findByRole('button', { name: /N172SP/ });
    expect(row).toHaveTextContent(/^N172SPCessna 172S Skyhawk/);
    expect(within(row).getByText('GO')).toBeInTheDocument();
  });

  it('marks an aircraft whose insurance has lapsed NO-GO in the list', async () => {
    const user = setupUser();
    server.use(
      ...registerFinds([
        makeVerifiedAircraft({ insurance_is_current: false, insurance_expiration: '2026-01-01' }),
      ]),
    );

    renderPage();
    await search(user, 'cessna');

    const row = await screen.findByRole('button', { name: /N172SP/ });
    expect(within(row).getByText('NO-GO')).toBeInTheDocument();
  });

  it('marks a current policy nobody has verified NO-GO, read out as not verified', async () => {
    const user = setupUser();
    server.use(...registerFinds([makeVerifiedAircraft({ insurance_verification: NOT_VERIFIED })]));

    renderPage();
    await search(user, 'cessna');

    const row = await screen.findByRole('button', { name: /N172SP/ });
    expect(row).toHaveTextContent(/Not verifiedNO-GO$/);
  });

  it('marks an aircraft the coverage policy excludes NO-GO, read out as not covered', async () => {
    const user = setupUser();
    server.use(
      ...registerFinds([
        makeVerifiedAircraft({
          category: 'helicopter',
          coverage: { excluded: true, reason: 'Not covered: helicopters are excluded' },
        }),
      ]),
    );

    renderPage();
    await search(user, 'cessna');

    const row = await screen.findByRole('button', { name: /N172SP/ });
    expect(row).toHaveTextContent(/Not coveredNO-GO$/);
  });

  it('marks an aircraft whose policy is about to expire GO in the list', async () => {
    const user = setupUser();
    server.use(
      ...registerFinds([
        makeVerifiedAircraft({ insurance_is_current: true, insurance_expiration: '2026-10-10' }),
      ]),
    );

    renderPage();
    await search(user, 'cessna');

    const row = await screen.findByRole('button', { name: /N172SP/ });
    expect(within(row).getByText('GO')).toBeInTheDocument();
  });

  it('opens the card for the aircraft the leader picks and keeps it in the URL', async () => {
    const user = setupUser();
    const asked: string[] = [];
    server.use(
      ...registerFinds([makeVerifiedAircraft()]),
      http.get(`${API}/leader/aircraft`, ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('n_number') ?? '');
        return HttpResponse.json(makeVerifiedAircraft());
      }),
    );

    const { router } = renderPage();
    await search(user, 'cessna');
    await user.click(await screen.findByRole('button', { name: /N172SP/ }));

    expect(await screen.findByText('INSURED')).toBeInTheDocument();
    expect(router.state.location.search).toBe('?aircraft=N172SP');
    expect(asked).toEqual(['N172SP']);
  });

  it('goes back to the search from the card', async () => {
    const user = userEvent.setup();
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeVerifiedAircraft())));

    const { router } = renderPage('/leader/aircraft?aircraft=N172SP');
    expect(await screen.findByText('INSURED')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Back to search/ }));
    expect(screen.getByLabelText(SEARCH_LABEL)).toBeInTheDocument();
    expect(router.state.location.search).toBe('');
  });

  it('says so when nothing in the register matches', async () => {
    const user = setupUser();
    server.use(...registerFinds([]));

    renderPage();
    await search(user, 'zeppelin');

    expect(await screen.findByText('No aircraft matches that')).toBeInTheDocument();
  });

  it('has no Check aircraft button: the results are the answer', () => {
    renderPage();
    expect(screen.queryByRole('button', { name: /Check aircraft/ })).not.toBeInTheDocument();
  });
});

describe('LeaderAircraftPage card', () => {
  it('reads the registration from the query string, normalized', async () => {
    const asked: string[] = [];
    server.use(
      http.get(`${API}/leader/aircraft`, ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('n_number') ?? '');
        return HttpResponse.json(makeVerifiedAircraft());
      }),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=n-172sp' });

    expect(await screen.findByRole('heading', { name: 'N172SP' })).toBeInTheDocument();
    expect(asked).toEqual(['N172SP']);
  });

  it('says NOT INSURED when the policy has run out', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeVerifiedAircraft({ insurance_is_current: false, insurance_expiration: '2026-01-01' }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('NOT INSURED')).toBeInTheDocument();
    expect(screen.getByText('Coverage has expired')).toBeInTheDocument();
  });

  it('says INSURED with a warning when the policy expires soon', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-09-24T12:00:00Z'));
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeVerifiedAircraft({ insurance_is_current: true, insurance_expiration: '2026-10-10' }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('INSURED')).toBeInTheDocument();
    expect(screen.getByText('Coverage expires soon')).toBeInTheDocument();
  });

  it('says NOT INSURED when there is no policy at all', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeVerifiedAircraft({ insurance_is_current: false, insurance_expiration: null }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('NOT INSURED')).toBeInTheDocument();
    expect(screen.getByText('No policy on file')).toBeInTheDocument();
  });

  it('says NOT COVERED, with the reason, for an aircraft the policy excludes', async () => {
    const reason = "Not covered: helicopters are excluded by CalDART's policy";
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeVerifiedAircraft({ category: 'helicopter', coverage: { excluded: true, reason } }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('NOT COVERED')).toBeInTheDocument();
    expect(screen.getByText("helicopters are excluded by CalDART's policy")).toHaveClass(
      'leader-verdict__why',
    );
  });

  it('says the category is not recorded beside a recorded airworthiness', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeVerifiedAircraft({
            category: '',
            airworthiness: 'standard',
            coverage: { excluded: false, reason: 'Category not recorded' },
          }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('Category not recorded · Standard')).toBeInTheDocument();
  });

  it('says when no category is recorded', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(
          makeVerifiedAircraft({
            category: '',
            airworthiness: '',
            coverage: { excluded: false, reason: 'Category not recorded' },
          }),
        ),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('Category not recorded')).toBeInTheDocument();
  });

  it('lists the members who fly it with their own currency', async () => {
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeVerifiedAircraft())));
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    expect(screen.getByText('Member current')).toBeInTheDocument();
    expect(screen.getByText('Medical current')).toBeInTheDocument();
  });

  it('says when the record was last written and who wrote it', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(makeVerifiedAircraft({ updated_by: { id: 4, name: 'Dana Fiske' } })),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    const row = await screen.findByText('Last updated');
    expect(row.parentElement).toHaveTextContent('Last updated09/01/2026 by Dana Fiske');
  });

  it('gives the date alone when nobody is recorded against the last write', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(makeVerifiedAircraft({ updated_by: null })),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    const row = await screen.findByText('Last updated');
    expect(row.parentElement).toHaveTextContent('Last updated09/01/2026');
  });

  it('shows the liability limits the leader has to check', async () => {
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeVerifiedAircraft())));
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText(/\$1,000,000/)).toBeInTheDocument();
    expect(screen.getByText(/\$100,000/)).toBeInTheDocument();
  });

  it('explains an unknown registration', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N0000X' });

    expect(await screen.findByText(/N0000X is not in the register/)).toBeInTheDocument();
  });

  it('goes back to the search from an unknown registration', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    const { router } = renderPage('/leader/aircraft?aircraft=N0000X');
    expect(await screen.findByText(/N0000X is not in the register/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Search again' }));
    expect(screen.getByLabelText(SEARCH_LABEL)).toBeInTheDocument();
    expect(router.state.location.search).toBe('');
  });

  it('says NOT VERIFIED when a current policy has not been verified', async () => {
    server.use(
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(makeVerifiedAircraft({ insurance_verification: NOT_VERIFIED })),
      ),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('NOT VERIFIED')).toBeInTheDocument();
    expect(screen.getByText('Coverage is current but not verified')).toBeInTheDocument();
  });

  it('marks the insurance row with who verified it and when', async () => {
    server.use(http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeVerifiedAircraft())));
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    const row = await screen.findByText('Insurance');
    expect(row.parentElement).toHaveTextContent(/Verified by Dana Leader on 05\/01\/2026$/);
  });

  it('offers a verifier Verify, and verifies the insurance from the card', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(
      signedInAs(makeUser({ roles: ['member', 'verifier'] })),
      http.get(`${API}/leader/aircraft`, () =>
        HttpResponse.json(makeVerifiedAircraft({ insurance_verification: NOT_VERIFIED })),
      ),
      ...verificationHandlers(calls),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    await user.click(await screen.findByRole('button', { name: 'Verify' }));
    await user.click(screen.getByLabelText('Insurance verified'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.aircraft).toEqual([{ aircraftId: 1, body: { verified: true } }]);
  });

  it('offers no Verify to a reader without a verifying role', async () => {
    server.use(
      signedInAs(makeUser({ roles: ['member'] })),
      http.get(`${API}/leader/aircraft`, () => HttpResponse.json(makeVerifiedAircraft())),
    );
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft?aircraft=N172SP' });

    expect(await screen.findByText('INSURED')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument();
  });

  it('asks nothing until a registration is given', () => {
    renderWithProviders(<LeaderAircraftPage />, { route: '/leader/aircraft' });
    expect(screen.queryByText(/INSURED/)).not.toBeInTheDocument();
  });
});
