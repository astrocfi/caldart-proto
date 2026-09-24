import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { AdminDart } from '@/portal/api/types';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { DartsPage } from './DartsPage';

function makeDart(overrides: Partial<AdminDart> = {}): AdminDart {
  return {
    id: 1,
    name: 'Palo Alto',
    airport_identifiers: 'PAO',
    city: 'Palo Alto',
    website_url: '',
    contacts: [],
    is_active: true,
    member_count: 0,
    page_count: 0,
    ...overrides,
  };
}

const NAPA = makeDart({ id: 2, name: 'Napa', airport_identifiers: 'APC', city: 'Napa' });

/** Serve `rows` from `/admin/darts`, signed in as an account administrator. */
function stubList(rows: AdminDart[] = [makeDart(), NAPA]) {
  server.use(
    signedInAs(makeUser({ roles: ['member', 'account_admin'] })),
    http.get(`${API}/admin/darts`, () => HttpResponse.json(rows)),
  );
}

function renderPage() {
  renderWithProviders(<DartsPage />, { route: '/admin/darts' });
}

describe('DartsPage', () => {
  it('lists every DART with its airport and town', async () => {
    stubList();
    renderPage();

    const cells = await screen.findAllByRole('cell', { name: 'Napa' });
    const row = cells[0]?.closest('tr');
    expect(within(row as HTMLElement).getByText('APC')).toBeInTheDocument();
  });

  it('says which DARTs are retired', async () => {
    stubList([makeDart({ is_active: false })]);
    renderPage();

    expect(await screen.findByText('Retired')).toBeInTheDocument();
  });

  it('posts a new DART', async () => {
    const user = userEvent.setup();
    let posted: unknown = null;
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(makeDart({ id: 3, name: 'Hayward' }), { status: 201 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.type(screen.getByLabelText('Name*'), 'Hayward');
    await user.type(screen.getByLabelText('Airports*'), 'hwd');
    await user.type(screen.getByLabelText('Town'), 'Hayward');
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    await waitFor(() =>
      expect(posted).toMatchObject({
        name: 'Hayward',
        airport_identifiers: 'HWD',
        city: 'Hayward',
        is_active: true,
      }),
    );
  });

  it('refuses to send a DART with no airport', async () => {
    const user = userEvent.setup();
    let asked = false;
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, () => {
        asked = true;
        return HttpResponse.json(makeDart(), { status: 201 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.type(screen.getByLabelText('Name*'), 'Nowhere');
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    expect(await screen.findByText('Give the DART at least one airport.')).toBeInTheDocument();
    expect(asked).toBe(false);
  });

  it('sends the people who run the DART with it', async () => {
    const user = userEvent.setup();
    let posted: { contacts?: unknown } | null = null;
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, async ({ request }) => {
        posted = (await request.json()) as { contacts?: unknown };
        return HttpResponse.json(makeDart({ id: 4 }), { status: 201 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.type(screen.getByLabelText('Name*'), 'Napa');
    await user.type(screen.getByLabelText('Airports*'), 'APC');
    await user.type(screen.getByLabelText('Name'), 'Helen Marchetti');
    await user.type(screen.getByLabelText('Title'), 'DART leader');
    await user.type(screen.getByLabelText('Phone'), '7075550133');
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    await waitFor(() =>
      expect(posted?.contacts).toEqual([
        { name: 'Helen Marchetti', title: 'DART leader', phone: '707-555-0133', email: '' },
      ]),
    );
  });

  it('leaves a contact row nobody filled in out of the body', async () => {
    const user = userEvent.setup();
    let posted: { contacts?: unknown } | null = null;
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, async ({ request }) => {
        posted = (await request.json()) as { contacts?: unknown };
        return HttpResponse.json(makeDart({ id: 5 }), { status: 201 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.type(screen.getByLabelText('Name*'), 'Napa');
    await user.type(screen.getByLabelText('Airports*'), 'APC');
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    await waitFor(() => expect(posted?.contacts).toEqual([]));
  });

  it('refuses to send a DART with no name', async () => {
    const user = userEvent.setup();
    let asked = false;
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, () => {
        asked = true;
        return HttpResponse.json(makeDart(), { status: 201 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    expect(await screen.findByText('Give the DART a name.')).toBeInTheDocument();
    expect(asked).toBe(false);
  });

  it('shows what the API rejected beside the field', async () => {
    const user = userEvent.setup();
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, () =>
        HttpResponse.json({ name: ['A DART with that name already exists.'] }, { status: 400 }),
      ),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.type(screen.getByLabelText('Name*'), 'Napa');
    await user.type(screen.getByLabelText('Airports*'), 'APC');
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    expect(await screen.findByText('A DART with that name already exists.')).toBeInTheDocument();
  });

  it('edits a DART through the same form', async () => {
    const user = userEvent.setup();
    let patched: unknown = null;
    stubList([makeDart()]);
    server.use(
      http.patch(`${API}/admin/darts/1`, async ({ request }) => {
        patched = await request.json();
        return HttpResponse.json(makeDart({ city: 'Mountain View' }));
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const town = screen.getByLabelText('Town');
    await user.clear(town);
    await user.type(town, 'Mountain View');
    await user.click(screen.getByRole('button', { name: 'Save DART' }));

    await waitFor(() => expect(patched).toMatchObject({ city: 'Mountain View' }));
  });

  it('will not offer to delete a DART somebody is on', async () => {
    stubList([makeDart({ member_count: 4 })]);
    renderPage();

    expect(await screen.findByRole('button', { name: 'Delete' })).toBeDisabled();
  });

  it('asks before deleting a DART nobody is on', async () => {
    const user = userEvent.setup();
    let deleted = false;
    stubList([makeDart()]);
    server.use(
      http.delete(`${API}/admin/darts/1`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(deleted).toBe(false);

    await user.click(screen.getByRole('button', { name: 'Delete for good' }));
    await waitFor(() => expect(deleted).toBe(true));
  });
});
