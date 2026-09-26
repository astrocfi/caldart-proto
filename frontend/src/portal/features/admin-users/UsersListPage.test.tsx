import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { User } from '@/portal/api/types';
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

/** Records every `/admin/users` query the page issues, and answers from `rows`. */
function stubList(rows: User[] = [MARTA, PRIYA]) {
  const seen: URLSearchParams[] = [];
  server.use(
    signedInAs(makeUser({ roles: ['member', 'user_admin'] })),
    http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
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

    expect(await screen.findByRole('link', { name: 'Marta Reyes' })).toHaveAttribute(
      'href',
      '/admin/users/1',
    );
    const priyaRow = screen.getByRole('link', { name: 'Priya Raman' }).closest('tr')!;
    expect(within(priyaRow).getByText('DART leader')).toBeInTheDocument();
    expect(within(priyaRow).getByText('Deactivated')).toBeInTheDocument();
    expect(screen.getByText('2 accounts')).toBeInTheDocument();
  });

  it('sends the search box to the API and narrows the table', async () => {
    const seen = stubList();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(<UsersListPage />);
    await screen.findByRole('link', { name: 'Marta Reyes' });

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
