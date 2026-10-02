import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportColumn, User } from '@/portal/api/types';
import { API, CURRENT_MEMBERSHIP, NO_MEMBERSHIP, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { UsersListPage } from './UsersListPage';

const ROLES = [
  { slug: 'member', description: 'Own profile and members-only content.' },
  { slug: 'dart_leader', description: 'Look up any member.' },
  { slug: 'user_admin', description: 'List users and assign roles.' },
];

const MARTA = makeUser({
  id: 1,
  email: 'marta@example.org',
  first_name: 'Marta',
  last_name: 'Reyes',
  roles: ['member'],
  membership: CURRENT_MEMBERSHIP,
});

const PRIYA = makeUser({
  id: 2,
  email: 'priya@example.org',
  first_name: 'Priya',
  last_name: 'Raman',
  roles: ['member', 'dart_leader'],
  membership: NO_MEMBERSHIP,
  is_active: false,
});

const GIL = makeUser({
  id: 3,
  email: 'gil@example.org',
  first_name: 'Gil',
  last_name: 'Ivers',
  roles: [],
  membership: NO_MEMBERSHIP,
  kind: 'donor',
});

/** The registry `GET /reports/roles/columns` answers with, trimmed to four. */
const COLUMNS: ReportColumn[] = [
  { key: 'role', label: 'Role', default: true },
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'city', label: 'City', default: false },
];

/** The title the disabled export controls carry while Donor is chosen. */
const DONOR_TITLE = 'A donor holds no role, so the roles report lists nobody.';

/** The title the disabled export controls carry while Member is the role. */
const MEMBER_TITLE = 'The roles report has no section for Member, so it lists nobody.';

/** Records every `/admin/users` query the page issues, and answers from `rows`. */
function stubList(rows: User[] = [MARTA, PRIYA]) {
  const seen: URLSearchParams[] = [];
  server.use(
    signedInAs(makeUser({ roles: ['member', 'user_admin'] })),
    http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
    http.get(`${API}/reports/roles/columns`, () => HttpResponse.json(COLUMNS)),
    http.get(`${API}/admin/users`, ({ request }) => {
      const url = new URL(request.url);
      seen.push(url.searchParams);
      const role = url.searchParams.get('role');
      const isActive = url.searchParams.get('is_active');
      const kind = url.searchParams.get('kind');
      const search = (url.searchParams.get('search') ?? '').toLowerCase();
      const results = rows.filter(
        (row) =>
          (!role || row.roles.includes(role as User['roles'][number])) &&
          (!isActive || String(row.is_active) === isActive) &&
          (!kind || row.kind === kind) &&
          (!search ||
            `${row.first_name} ${row.last_name} ${row.email}`.toLowerCase().includes(search)),
      );
      return HttpResponse.json({ count: results.length, next: null, previous: null, results });
    }),
  );
  return seen;
}

describe('UsersListPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('lists accounts with their roles, membership, and status', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    await userEvent.selectOptions(screen.getByLabelText(/account status/i), '');

    expect(await screen.findByRole('link', { name: 'Marta Reyes' })).toHaveAttribute(
      'href',
      '/admin/users/1',
    );
    const priyaRow = (await screen.findByRole('link', { name: 'Priya Raman' })).closest('tr')!;
    expect(within(priyaRow).getByText('DART leader')).toBeInTheDocument();
    expect(within(priyaRow).getByText('Deactivated')).toBeInTheDocument();
    expect(screen.getByText('2 accounts')).toBeInTheDocument();
  });

  it('starts on active accounts only', async () => {
    const seen = stubList();
    renderWithProviders(<UsersListPage />);

    await waitFor(() => expect(seen[0]?.get('is_active')).toBe('true'));
  });

  it('shows Active only as the chosen account status', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);

    expect(await screen.findByLabelText(/account status/i)).toHaveDisplayValue('Active only');
  });

  it('offers the account statuses in order', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);

    const options = within(await screen.findByLabelText(/account status/i)).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      'Active and deactivated',
      'Active only',
      'Deactivated only',
    ]);
  });

  it('draws Search, then Kind of account, then Account status', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    const fields = [
      screen.getByLabelText(/search/i),
      screen.getByLabelText(/kind of account/i),
      screen.getByLabelText(/account status/i),
    ];
    const order = fields.map((field) =>
      Array.from(document.querySelectorAll('input, select')).indexOf(field),
    );
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it('exports the roles report with the default columns when nothing is filtered', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('button', { name: 'Columns' });

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      '/api/v1/reports/roles/export.csv?columns=role%2Cname%2Cemail',
    );
  });

  it('carries the search, role, kind, and columns into both export links', async () => {
    stubList();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('button', { name: 'Columns' });

    await user.type(screen.getByLabelText(/search/i), 'reyes');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));
    await user.click(screen.getByRole('button', { name: 'DART leader' }));
    await user.selectOptions(screen.getByLabelText(/kind of account/i), 'friend');
    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'City' }));

    const query = '?search=reyes&role=dart_leader&kind=friend&columns=role%2Cname%2Cemail%2Ccity';
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
        'href',
        `/api/v1/reports/roles/export.csv${query}`,
      ),
    );
    expect(screen.getByRole('link', { name: 'Export PDF' })).toHaveAttribute(
      'href',
      `/api/v1/reports/roles/export.pdf${query}`,
    );
  });

  it('leaves the account status out of the export links', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('button', { name: 'Columns' });

    await userEvent.selectOptions(screen.getByLabelText(/account status/i), 'false');

    const href = screen.getByRole('link', { name: 'Export PDF' }).getAttribute('href') ?? '';
    expect(new URL(href, 'http://localhost').searchParams.has('is_active')).toBe(false);
  });

  it('disables both exports and the column chooser while Donor is chosen', async () => {
    stubList([MARTA, GIL]);
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('button', { name: 'Columns' });

    await userEvent.selectOptions(screen.getByLabelText(/kind of account/i), 'donor');

    const controls = ['Export CSV', 'Export PDF', 'Columns'].map((name) =>
      screen.getByRole('button', { name }),
    );
    expect(controls.map((control) => [control.hasAttribute('disabled'), control.title])).toEqual([
      [true, DONOR_TITLE],
      [true, DONOR_TITLE],
      [true, DONOR_TITLE],
    ]);
  });

  it('offers no export link while Donor is chosen', async () => {
    stubList([MARTA, GIL]);
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('button', { name: 'Columns' });

    await userEvent.selectOptions(screen.getByLabelText(/kind of account/i), 'donor');

    expect(screen.queryByRole('link', { name: /Export/ })).not.toBeInTheDocument();
  });

  it('disables both exports and the column chooser while Member is the role', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('button', { name: 'Columns' });

    await userEvent.click(screen.getByRole('button', { name: 'Member' }));

    const controls = ['Export CSV', 'Export PDF', 'Columns'].map((name) =>
      screen.getByRole('button', { name }),
    );
    expect(controls.map((control) => [control.hasAttribute('disabled'), control.title])).toEqual([
      [true, MEMBER_TITLE],
      [true, MEMBER_TITLE],
      [true, MEMBER_TITLE],
    ]);
  });

  it('says the columns could not be loaded when the registry fails', async () => {
    stubList();
    server.use(
      http.get(`${API}/reports/roles/columns`, () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<UsersListPage />);

    expect(
      await screen.findByText(
        'The columns could not be loaded; the downloads carry the default columns.',
      ),
    ).toBeInTheDocument();
  });

  it('exports without a columns parameter when the registry fails', async () => {
    stubList();
    server.use(
      http.get(`${API}/reports/roles/columns`, () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<UsersListPage />);
    await screen.findByText(/the columns could not be loaded/i);

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      '/api/v1/reports/roles/export.csv',
    );
  });

  it('sends the search box to the API and narrows the table', async () => {
    const seen = stubList();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });
    await user.selectOptions(screen.getByLabelText(/account status/i), '');

    await user.type(screen.getByLabelText(/search/i), 'priya');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));

    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'Marta Reyes' })).not.toBeInTheDocument(),
    );
    expect(screen.getByRole('link', { name: 'Priya Raman' })).toBeInTheDocument();
    expect(seen.at(-1)?.get('search')).toBe('priya');
  });

  it('filters by role from the chips and can clear the filter', async () => {
    const seen = stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    await userEvent.click(screen.getByRole('button', { name: 'DART leader' }));

    await waitFor(() => expect(seen.at(-1)?.get('role')).toBe('dart_leader'));
    expect(screen.getByRole('button', { name: 'DART leader' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'Marta Reyes' })).not.toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole('button', { name: 'DART leader' }));
    await waitFor(() => expect(seen.at(-1)?.get('role')).toBeNull());
    expect(await screen.findByRole('link', { name: 'Marta Reyes' })).toBeInTheDocument();
  });

  it('filters by account status', async () => {
    const seen = stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    await userEvent.selectOptions(screen.getByLabelText(/account status/i), 'false');

    await waitFor(() => expect(seen.at(-1)?.get('is_active')).toBe('false'));
    expect(await screen.findByRole('link', { name: 'Priya Raman' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Marta Reyes' })).not.toBeInTheDocument();
  });

  it('filters by a bounced address', async () => {
    const seen = stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    await userEvent.selectOptions(screen.getByLabelText('Email'), 'Email bounced');

    await waitFor(() => expect(seen.at(-1)?.get('email_bounced')).toBe('true'));
  });

  it('carries the bounce filter into the exports', async () => {
    stubList();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    await userEvent.selectOptions(screen.getByLabelText('Email'), 'Email bounced');

    const href = screen.getByRole('link', { name: /csv/i }).getAttribute('href') ?? '';
    expect(new URL(href, 'http://localhost').searchParams.get('email_bounced')).toBe('true');
  });

  it('names the kind of each account', async () => {
    stubList([MARTA, GIL]);
    renderWithProviders(<UsersListPage />);

    const gilRow = (await screen.findByRole('link', { name: 'Gil Ivers' })).closest('tr')!;
    expect(within(gilRow).getByText('Donor')).toBeInTheDocument();
  });

  it('filters by kind of account', async () => {
    const seen = stubList([MARTA, GIL]);
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

    await userEvent.selectOptions(screen.getByLabelText(/kind of account/i), 'donor');

    await waitFor(() => expect(seen.at(-1)?.get('kind')).toBe('donor'));
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'Marta Reyes' })).not.toBeInTheDocument(),
    );
    expect(screen.getByRole('link', { name: 'Gil Ivers' })).toBeInTheDocument();
  });

  it('shows an empty state when nothing matches', async () => {
    stubList([]);
    renderWithProviders(<UsersListPage />);

    expect(await screen.findByText(/no accounts match those filters/i)).toBeInTheDocument();
  });
});
