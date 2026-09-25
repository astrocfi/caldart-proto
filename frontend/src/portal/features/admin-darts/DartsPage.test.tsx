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
    website_url: '',
    contacts: [],
    is_active: true,
    member_count: 0,
    page_count: 0,
    ...overrides,
  };
}

const NAPA = makeDart({ id: 2, name: 'Napa', airport_identifiers: 'APC' });

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
  it('lists every DART with its airports', async () => {
    stubList();
    renderPage();

    const cells = await screen.findAllByRole('cell', { name: 'Napa' });
    const row = cells[0]?.closest('tr');
    expect(within(row as HTMLElement).getByText('APC')).toBeInTheDocument();
  });

  it('has no town column', async () => {
    stubList();
    renderPage();

    await screen.findAllByRole('cell', { name: 'Napa' });
    expect(screen.queryByRole('columnheader', { name: 'Town' })).not.toBeInTheDocument();
  });

  it('links the member count to that DART on the member list', async () => {
    stubList([makeDart({ member_count: 4 })]);
    renderPage();

    const link = await screen.findByRole('link', { name: '4' });
    expect(link).toHaveAttribute('href', '/admin/members?dart=1');
  });

  it('says which DARTs are inactive', async () => {
    stubList([makeDart({ is_active: false })]);
    renderPage();

    expect(await screen.findByText('Inactive')).toBeInTheDocument();
  });

  it('says which DARTs are active', async () => {
    stubList([makeDart()]);
    renderPage();

    expect(await screen.findByText('Active')).toBeInTheDocument();
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
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    await waitFor(() =>
      expect(posted).toMatchObject({
        name: 'Hayward',
        airport_identifiers: 'HWD',
        is_active: true,
      }),
    );
  });

  it('sends no town with a new DART', async () => {
    const user = userEvent.setup();
    let posted: Record<string, unknown> | null = null;
    stubList();
    server.use(
      http.post(`${API}/admin/darts`, async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeDart({ id: 3, name: 'Hayward' }), { status: 201 });
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    await user.type(screen.getByLabelText('Name*'), 'Hayward');
    await user.type(screen.getByLabelText('Airports*'), 'hwd');
    await user.click(screen.getByRole('button', { name: 'Add DART' }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted).not.toHaveProperty('city');
  });

  it('asks for no town', async () => {
    const user = userEvent.setup();
    stubList();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    expect(screen.queryByLabelText('Town')).not.toBeInTheDocument();
  });

  it('asks whether the DART is active', async () => {
    const user = userEvent.setup();
    stubList();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    expect(
      screen.getByLabelText('Active — untick to make the DART inactive without losing its history'),
    ).toBeInTheDocument();
  });

  it('heads the contacts fieldset DART management', async () => {
    const user = userEvent.setup();
    stubList();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add a DART' }));
    expect(screen.getByRole('group', { name: /DART management/ })).toBeInTheDocument();
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
        return HttpResponse.json(makeDart({ name: 'Mountain View' }));
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const name = screen.getByLabelText('Name*');
    await user.clear(name);
    await user.type(name, 'Mountain View');
    await user.click(screen.getByRole('button', { name: 'Save DART' }));

    await waitFor(() => expect(patched).toMatchObject({ name: 'Mountain View' }));
  });

  it('offers no delete from the list', async () => {
    stubList([makeDart()]);
    renderPage();

    await screen.findByRole('button', { name: 'Edit' });
    expect(screen.queryByRole('button', { name: 'Delete this DART' })).not.toBeInTheDocument();
  });

  it('offers the delete for a DART somebody is on', async () => {
    const user = userEvent.setup();
    stubList([makeDart({ member_count: 4 })]);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));

    expect(screen.getByRole('button', { name: 'Delete this DART' })).toBeEnabled();
  });

  it('warns what a delete leaves behind before it is confirmed', async () => {
    const user = userEvent.setup();
    stubList([makeDart({ member_count: 4, page_count: 2 })]);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Delete this DART' }));

    expect(
      screen.getByText(
        'Deleting Palo Alto makes its 4 members unaffiliated and unlinks 2 website pages. ' +
          'This cannot be undone.',
      ),
    ).toBeInTheDocument();
  });

  it('warns about nothing for a DART nothing points at', async () => {
    const user = userEvent.setup();
    stubList([makeDart()]);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Delete this DART' }));

    expect(screen.queryByText(/This cannot be undone/)).not.toBeInTheDocument();
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

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Delete this DART' }));
    expect(deleted).toBe(false);

    await user.click(screen.getByRole('button', { name: 'Delete for good' }));
    await waitFor(() => expect(deleted).toBe(true));
  });

  it('keeps the DART when the confirmation is declined', async () => {
    const user = userEvent.setup();
    stubList([makeDart()]);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Delete this DART' }));
    await user.click(screen.getByRole('button', { name: 'Keep' }));

    expect(screen.getByRole('button', { name: 'Delete this DART' })).toBeInTheDocument();
  });

  it('offers the delete again when the delete fails', async () => {
    const user = userEvent.setup();
    stubList([makeDart()]);
    server.use(
      http.delete(`${API}/admin/darts/1`, () =>
        HttpResponse.json({ detail: 'That DART was not deleted.' }, { status: 500 }),
      ),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Delete this DART' }));
    await user.click(screen.getByRole('button', { name: 'Delete for good' }));

    expect(await screen.findByRole('button', { name: 'Delete this DART' })).toBeInTheDocument();
  });

  it('moves a person down the list and saves the new order', async () => {
    const user = userEvent.setup();
    let patched: { contacts?: { name: string }[] } | null = null;
    stubList([
      makeDart({
        contacts: [
          { id: 1, name: 'Helen', title: 'DART leader', phone: '', email: '' },
          { id: 2, name: 'Sam', title: 'Deputy', phone: '', email: '' },
        ],
      }),
    ]);
    server.use(
      http.patch(`${API}/admin/darts/1`, async ({ request }) => {
        patched = (await request.json()) as { contacts?: { name: string }[] };
        return HttpResponse.json(makeDart());
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Move person 1 down' }));
    await user.click(screen.getByRole('button', { name: 'Save DART' }));

    await waitFor(() =>
      expect(patched?.contacts?.map((one) => one.name)).toEqual(['Sam', 'Helen']),
    );
  });

  it('moves a person up the list and saves the new order', async () => {
    const user = userEvent.setup();
    let patched: { contacts?: { name: string }[] } | null = null;
    stubList([
      makeDart({
        contacts: [
          { id: 1, name: 'Helen', title: 'DART leader', phone: '', email: '' },
          { id: 2, name: 'Sam', title: 'Deputy', phone: '', email: '' },
        ],
      }),
    ]);
    server.use(
      http.patch(`${API}/admin/darts/1`, async ({ request }) => {
        patched = (await request.json()) as { contacts?: { name: string }[] };
        return HttpResponse.json(makeDart());
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Move person 2 up' }));
    await user.click(screen.getByRole('button', { name: 'Save DART' }));

    await waitFor(() =>
      expect(patched?.contacts?.map((one) => one.name)).toEqual(['Sam', 'Helen']),
    );
  });

  it('cannot move the first person up or the last person down', async () => {
    const user = userEvent.setup();
    stubList([
      makeDart({
        contacts: [
          { id: 1, name: 'Helen', title: 'DART leader', phone: '', email: '' },
          { id: 2, name: 'Sam', title: 'Deputy', phone: '', email: '' },
        ],
      }),
    ]);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));

    expect(screen.getByRole('button', { name: 'Move person 1 up' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Move person 2 down' })).toBeDisabled();
  });

  it('moves a person with a bare icon button', async () => {
    const user = userEvent.setup();
    stubList([
      makeDart({
        contacts: [
          { id: 1, name: 'Helen', title: 'DART leader', phone: '', email: '' },
          { id: 2, name: 'Sam', title: 'Deputy', phone: '', email: '' },
        ],
      }),
    ]);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));

    expect(screen.getByRole('button', { name: 'Move person 1 down' })).toHaveClass('icon-button');
  });

  it('takes a person off the list with the trashcan', async () => {
    const user = userEvent.setup();
    let patched: { contacts?: { name: string }[] } | null = null;
    stubList([
      makeDart({
        contacts: [
          { id: 1, name: 'Helen', title: 'DART leader', phone: '', email: '' },
          { id: 2, name: 'Sam', title: 'Deputy', phone: '', email: '' },
        ],
      }),
    ]);
    server.use(
      http.patch(`${API}/admin/darts/1`, async ({ request }) => {
        patched = (await request.json()) as { contacts?: { name: string }[] };
        return HttpResponse.json(makeDart());
      }),
    );
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('button', { name: 'Remove person 1' }));
    await user.click(screen.getByRole('button', { name: 'Save DART' }));

    await waitFor(() => expect(patched?.contacts?.map((one) => one.name)).toEqual(['Sam']));
  });
});
