import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { EmailType, EmailTypeInput } from '@/portal/api/types';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { headerWords } from '@test/table';
import { EmailTypesPage, inUseReason, sendersText } from './EmailTypesPage';

function makeType(overrides: Partial<EmailType> = {}): EmailType {
  return {
    id: 1,
    name: 'Operational',
    slug: 'operational',
    description: 'News about how CalDART runs.',
    allow_opt_out: true,
    sender_roles: ['dart_leader', 'management'],
    position: 1,
    in_use: false,
    ...overrides,
  };
}

const FUNDRAISING = makeType({
  id: 2,
  name: 'Fundraising',
  slug: 'fundraising',
  description: 'Appeals for donations.',
  sender_roles: ['management'],
  allow_opt_out: false,
  position: 2,
});

interface Captured {
  created: EmailTypeInput[];
  updated: { id: string; body: EmailTypeInput }[];
  deleted: string[];
}

/** Serve `rows` from `/email-types` as a system administrator, recording every write. */
function stubTypes(rows: EmailType[] = [makeType(), FUNDRAISING]): Captured {
  const captured: Captured = { created: [], updated: [], deleted: [] };
  server.use(
    signedInAs(makeUser({ roles: ['member', 'system_admin'] })),
    http.get(`${API}/email-types`, () => HttpResponse.json(rows)),
    http.post(`${API}/email-types`, async ({ request }) => {
      const body = (await request.json()) as EmailTypeInput;
      captured.created.push(body);
      return HttpResponse.json(makeType({ id: 9, ...body, slug: 'x', position: 3 }), {
        status: 201,
      });
    }),
    http.put(`${API}/email-types/:id`, async ({ params, request }) => {
      const body = (await request.json()) as EmailTypeInput;
      captured.updated.push({ id: String(params.id), body });
      return HttpResponse.json(makeType({ id: Number(params.id), ...body, position: 1 }));
    }),
    http.delete(`${API}/email-types/:id`, ({ params }) => {
      captured.deleted.push(String(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return captured;
}

function renderPage() {
  renderWithProviders(<EmailTypesPage />, { route: '/bulk-email/types' });
}

/** The table row holding `name`. */
async function rowOf(name: string): Promise<HTMLElement> {
  const cell = await screen.findByRole('rowheader', { name });
  return cell.closest('tr') as HTMLElement;
}

describe('EmailTypesPage', () => {
  it('lists each type with who may send it and whether it can be turned off', async () => {
    stubTypes();
    renderPage();

    const row = await rowOf('Fundraising');
    expect(within(row).getByText('CalDART management')).toBeInTheDocument();
    expect(within(row).getByRole('cell', { name: 'No' })).toBeInTheDocument();
  });

  it('names a type nobody is named for as the system administrators’ alone', () => {
    expect(sendersText(makeType({ sender_roles: [] }))).toBe('System administrators only');
  });

  it('names every sending role in words', () => {
    expect(sendersText(makeType())).toBe('DART leader, CalDART management');
  });

  it('adds a type from the form', async () => {
    const captured = stubTypes();
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Add an email type' }));
    await user.type(screen.getByLabelText(/^Name/), 'Board news');
    await user.type(screen.getByLabelText(/^What it is for/), 'What the board decided.');
    await user.click(screen.getByRole('checkbox', { name: 'CalDART management' }));
    await user.click(screen.getByRole('button', { name: 'Add type' }));

    await waitFor(() =>
      expect(captured.created).toEqual([
        {
          name: 'Board news',
          description: 'What the board decided.',
          allow_opt_out: true,
          sender_roles: ['management'],
        },
      ]),
    );
    expect(await screen.findByText('Board news added.')).toBeInTheDocument();
  });

  it('shows a refused name beside the field', async () => {
    stubTypes();
    server.use(
      http.post(`${API}/email-types`, () =>
        HttpResponse.json({ name: ['Another email type already has this name.'] }, { status: 400 }),
      ),
    );
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Add an email type' }));
    await user.type(screen.getByLabelText(/^Name/), 'operational');
    await user.type(screen.getByLabelText(/^What it is for/), 'Again.');
    await user.click(screen.getByRole('button', { name: 'Add type' }));

    expect(await screen.findByText('Another email type already has this name.')).toBeVisible();
  });

  it('moves the focus into the form as it opens', async () => {
    stubTypes();
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Add an email type' }));

    expect(screen.getByRole('textbox', { name: /Name/ })).toHaveFocus();
  });

  it('closes the form on Escape and gives the focus back to the row it was opened from', async () => {
    stubTypes();
    renderPage();
    const user = userEvent.setup();

    const row = await rowOf('Fundraising');
    await user.click(within(row).getByRole('button', { name: 'Edit Fundraising' }));
    await user.keyboard('{Escape}');

    expect(
      within(await rowOf('Fundraising')).getByRole('button', { name: 'Edit Fundraising' }),
    ).toHaveFocus();
  });

  it('edits a type, starting from its settings', async () => {
    const captured = stubTypes();
    renderPage();
    const user = userEvent.setup();

    const row = await rowOf('Fundraising');
    await user.click(within(row).getByRole('button', { name: 'Edit Fundraising' }));
    expect(screen.getByRole('checkbox', { name: 'Recipients may turn it off' })).not.toBeChecked();
    await user.click(screen.getByRole('checkbox', { name: 'Recipients may turn it off' }));
    await user.click(screen.getByRole('checkbox', { name: 'DART leader' }));
    await user.click(screen.getByRole('button', { name: 'Save type' }));

    await waitFor(() =>
      expect(captured.updated).toEqual([
        {
          id: '2',
          body: {
            name: 'Fundraising',
            description: 'Appeals for donations.',
            allow_opt_out: true,
            sender_roles: ['dart_leader', 'management'],
          },
        },
      ]),
    );
  });

  it('asks before deleting a type', async () => {
    const captured = stubTypes();
    renderPage();
    const user = userEvent.setup();

    const row = await rowOf('Operational');
    await user.click(within(row).getByRole('button', { name: 'Delete Operational' }));
    expect(captured.deleted).toEqual([]);
    await user.click(within(row).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(captured.deleted).toEqual(['1']));
    expect(await screen.findByText('Operational deleted.')).toBeInTheDocument();
  });

  it('grays the trashcan of a type in use, saying why', async () => {
    stubTypes([makeType({ in_use: true })]);
    renderPage();

    const trashcan = within(await rowOf('Operational')).getByRole('button', {
      name: 'Delete Operational',
    });
    expect([trashcan.hasAttribute('disabled'), trashcan.getAttribute('title')]).toEqual([
      true,
      inUseReason(makeType()),
    ]);
  });

  it('starts each name at the left edge', async () => {
    stubTypes();
    renderPage();
    await rowOf('Operational');
    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveClass('data-table__identity');
  });

  it('puts the name first and Edit and the trashcan last', async () => {
    stubTypes();
    renderPage();
    await rowOf('Operational');
    const headers = screen.getAllByRole('columnheader').map(headerWords);
    expect([headers[0], headers.at(-1)]).toEqual(['Name', 'Actions']);
  });

  it('never lets the description narrow below a readable width', async () => {
    stubTypes();
    renderPage();
    await rowOf('Operational');
    expect(screen.getByRole('columnheader', { name: 'What it is for' })).toHaveStyle({
      width: '13rem',
    });
  });

  it('makes the actions wide enough for Edit beside an open delete confirmation', async () => {
    stubTypes();
    renderPage();
    await rowOf('Operational');
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toHaveStyle({ width: '12rem' });
  });

  it('says plainly why a type in use cannot be deleted', async () => {
    const refusal =
      'Operational has been used for a bulk email, so it cannot be deleted. To keep DART ' +
      'leaders and CalDART management from sending it, take their roles off it instead.';
    stubTypes();
    server.use(
      http.delete(`${API}/email-types/:id`, () =>
        HttpResponse.json({ detail: refusal }, { status: 400 }),
      ),
    );
    renderPage();
    const user = userEvent.setup();

    const row = await rowOf('Operational');
    await user.click(within(row).getByRole('button', { name: 'Delete Operational' }));
    await user.click(within(row).getByRole('button', { name: 'Delete' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(refusal);
  });
});
