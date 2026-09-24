import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MembersListPage } from './MembersListPage';
import { LIFETIME, makeRow } from '@test/fixtures/members';

/** The registry `GET /admin/members/columns` answers with, trimmed to five. */
const COLUMNS = [
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'dart', label: 'DART', default: true },
  { key: 'certificate_number', label: 'Certificate number', default: false },
  { key: 'state', label: 'State', default: false },
];

const DARTS = [
  { id: 3, name: 'Palo Alto', airport_identifiers: 'PAO', city: 'Palo Alto' },
  { id: 5, name: 'Napa', airport_identifiers: 'APC', city: 'Napa' },
];

/** Every request the list page makes, with the last member query recorded. */
let requestedUrls: string[] = [];

function lastMemberQuery(): URLSearchParams {
  const last = requestedUrls.at(-1);
  return new URLSearchParams(last ? new URL(last).search : '');
}

function listHandlers(rows = [makeRow()], count = rows.length) {
  return [
    http.get(`${API}/darts`, () => HttpResponse.json(DARTS)),
    http.get(`${API}/admin/members/columns`, () => HttpResponse.json(COLUMNS)),
    http.get(`${API}/admin/members`, ({ request }) => {
      requestedUrls.push(request.url);
      return HttpResponse.json({
        count,
        next: count > rows.length ? `${API}/admin/members?page=2` : null,
        previous: null,
        results: rows,
      });
    }),
  ];
}

function ShowSearch() {
  const location = useLocation();
  return <span data-testid="location-search">{location.search}</span>;
}

function renderList(route = '/admin/members') {
  return renderWithProviders(
    <Routes>
      <Route
        path="/admin/members"
        element={
          <>
            <MembersListPage />
            <ShowSearch />
          </>
        }
      />
      <Route path="/admin/members/:id" element={<p>member record</p>} />
      <Route path="/admin/members/new" element={<p>new member form</p>} />
    </Routes>,
    { route },
  );
}

beforeEach(() => {
  requestedUrls = [];
});

describe('MembersListPage', () => {
  it('shows five columns: pilot, name, DART, membership expiry, and email', async () => {
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const headers = screen.getAllByRole('columnheader').map((cell) => cell.textContent);
    expect(headers).toEqual(['Pilot', 'Name', 'DART', 'Membership Exp.', 'Email']);
  });

  it('ticks a pilot whose medical is in date and crosses one whose is not', async () => {
    server.use(
      ...listHandlers([
        makeRow(),
        makeRow({ user_id: 2, name: 'Bo Chen', medical_is_current: false }),
        makeRow({ user_id: 3, name: 'Cal Dunn', pilot_certificate_type: 'none' }),
      ]),
    );
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const table = within(screen.getByRole('table'));
    expect(table.getByText('Medical current')).toBeInTheDocument();
    expect(table.getByText('Medical expired')).toBeInTheDocument();
    expect(table.getByText('Not a pilot')).toBeInTheDocument();
  });

  it('marks the membership with a dot rather than a chip', async () => {
    server.use(
      ...listHandlers([
        makeRow(),
        makeRow({
          user_id: 2,
          name: 'Bo Chen',
          membership: {
            status: 'expired',
            expires_on: '2025-01-01',
            plan: 'Annual',
            is_lifetime: false,
          },
        }),
      ]),
    );
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const table = within(screen.getByRole('table'));
    expect(table.getByText('Current')).toBeInTheDocument();
    expect(table.getByText('Expired')).toBeInTheDocument();
    expect(table.queryByText('Expiring soon')).not.toBeInTheDocument();
    // The wordy chip is gone: the dot and the date carry it now.
    expect(table.queryByText('No membership')).not.toBeInTheDocument();
  });

  it('keeps every cell on one line and hangs the full value off the cell', async () => {
    server.use(
      ...listHandlers([
        makeRow({ email: 'ana.bracco.with.a.very.long.address@caldart.example.org' }),
      ]),
    );
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const table = screen.getByRole('table');
    expect(table.closest('.data-table')).toHaveClass('data-table--single-line');
    expect(within(table).getByRole('cell', { name: 'Palo Alto' })).toHaveAttribute(
      'title',
      'Palo Alto',
    );
  });

  it('sorts on every column, including Pilot and DART', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.click(screen.getByRole('button', { name: 'DART' }));
    await waitFor(() => expect(lastMemberQuery().get('ordering')).toBe('dart'));

    await user.click(screen.getByRole('button', { name: 'Pilot' }));
    await waitFor(() => expect(lastMemberQuery().get('ordering')).toBe('pilot'));
  });

  it('renders a row per member with its membership chip', async () => {
    server.use(
      ...listHandlers([
        makeRow(),
        makeRow({ user_id: 2, name: 'Bo Chen', email: 'bo@example.org', membership: LIFETIME }),
      ]),
    );
    renderList();

    expect(await screen.findByRole('link', { name: 'Ana Bracco' })).toHaveAttribute(
      'href',
      '/admin/members/1',
    );
    expect(screen.getByRole('link', { name: 'Bo Chen' })).toBeInTheDocument();
    expect(screen.getByText('Never expires')).toBeInTheDocument();
    expect(screen.getByText('2 members match these filters')).toBeInTheDocument();
  });

  it('shows an empty state when nothing matches', async () => {
    server.use(...listHandlers([], 0));
    renderList();
    expect(await screen.findByText('No members match these filters')).toBeInTheDocument();
  });

  it('sends a dropdown filter as a query parameter and puts it in the URL', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.selectOptions(screen.getByLabelText('Membership'), 'current');

    await waitFor(() => expect(lastMemberQuery().get('status')).toBe('current'));
    expect(screen.getByTestId('location-search')).toHaveTextContent('status=current');
  });

  it('searches as the name is typed, once the typing pauses', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.type(screen.getByLabelText('Search'), 'bracco');
    // The keystroke itself does not query: the list follows the pause.
    expect(lastMemberQuery().get('search')).toBeNull();

    await waitFor(() => expect(lastMemberQuery().get('search')).toBe('bracco'));
  });

  it('refuses a letter typed into the day count', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const days = screen.getByLabelText('Expiring within (days)');
    await user.type(days, '3a0');

    expect(days).toHaveValue('30');
  });

  it('combines several filters', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.selectOptions(screen.getByLabelText('DART'), '5');
    await user.selectOptions(screen.getByLabelText('Certificate'), 'commercial');
    await user.type(screen.getByLabelText('Expiring within (days)'), '30');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      const query = lastMemberQuery();
      expect(query.get('dart')).toBe('5');
      expect(query.get('certificate')).toBe('commercial');
      expect(query.get('expiring_within')).toBe('30');
    });
  });

  it('offers the DARTs the API knows about', async () => {
    server.use(...listHandlers());
    renderList();
    expect(await screen.findByRole('option', { name: 'Napa' })).toBeInTheDocument();
    expect(within(screen.getByLabelText('DART')).getAllByRole('option')).toHaveLength(3);
  });

  it('still renders when the DART list is unavailable', async () => {
    server.use(
      http.get(`${API}/darts`, () => HttpResponse.json({ detail: 'Not found.' }, { status: 404 })),
      ...listHandlers().slice(1),
    );
    renderList();
    expect(await screen.findByRole('link', { name: 'Ana Bracco' })).toBeInTheDocument();
    expect(within(await screen.findByLabelText('DART')).getAllByRole('option')).toHaveLength(1);
  });

  it('clears every filter', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList('/admin/members?status=expired&search=bracco');
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.click(screen.getByRole('button', { name: 'Clear' }));
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent(''));
    expect(lastMemberQuery().get('status')).toBeNull();
  });

  it('reads the filters back out of the URL on first load', async () => {
    server.use(...listHandlers());
    renderList('/admin/members?status=current&certificate=atp&ordering=-expires_on');
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const query = lastMemberQuery();
    expect(query.get('status')).toBe('current');
    expect(query.get('certificate')).toBe('atp');
    expect(query.get('ordering')).toBe('-expires_on');
    expect(screen.getByLabelText('Membership')).toHaveValue('current');
  });

  it('sorts server-side when a column header is clicked', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.click(screen.getByRole('button', { name: /Membership/ }));
    await waitFor(() => expect(lastMemberQuery().get('ordering')).toBe('expires_on'));

    await user.click(screen.getByRole('button', { name: /Membership/ }));
    await waitFor(() => expect(lastMemberQuery().get('ordering')).toBe('-expires_on'));
  });

  it('points the export buttons at the same filters', async () => {
    server.use(...listHandlers());
    renderList('/admin/members?status=current&dart=5&expiring_within=30');
    await screen.findByRole('link', { name: 'Ana Bracco' });

    const csv = screen.getByRole('link', { name: /Export CSV/ });
    const pdf = screen.getByRole('link', { name: /Export PDF/ });
    expect(csv).toHaveAttribute(
      'href',
      '/api/v1/admin/members/export.csv?status=current&dart=5&expiring_within=30' +
        '&columns=name%2Cemail%2Cdart',
    );
    expect(pdf.getAttribute('href')).toContain('/api/v1/admin/members/export.pdf?');
    expect(pdf.getAttribute('href')).toContain('dart=5');
  });

  it('exports the default columns when nothing is filtered', async () => {
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });
    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/members/export.csv?columns=name%2Cemail%2Cdart',
    );
  });

  it('offers every column the report can carry, with the defaults ticked', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    const panel = screen.getByRole('group', { name: /Columns to show and export/ });
    expect(within(panel).getByRole('checkbox', { name: 'Name' })).toBeChecked();
    expect(within(panel).getByRole('checkbox', { name: 'State' })).not.toBeChecked();
  });

  it('carries a chosen column into both export links', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'State' }));

    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/members/export.csv?columns=name%2Cemail%2Cdart%2Cstate',
    );
    expect(screen.getByRole('link', { name: /Export PDF/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/members/export.pdf?columns=name%2Cemail%2Cdart%2Cstate',
    );
  });

  it('drops a column the administrator unticks from the export links', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers());
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'DART' }));

    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/members/export.csv?columns=name%2Cemail',
    );
  });

  it('pages through a long list', async () => {
    const user = userEvent.setup();
    server.use(...listHandlers([makeRow()], 60));
    renderList();
    await screen.findByRole('link', { name: 'Ana Bracco' });

    expect(screen.getByText(/Showing 1–1 of 60/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(lastMemberQuery().get('page')).toBe('2'));
  });

  it('links to the new-member form', async () => {
    server.use(...listHandlers());
    renderList();
    expect(await screen.findByRole('link', { name: 'New member' })).toHaveAttribute(
      'href',
      '/admin/members/new',
    );
  });
});
