import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { FIELDS } from '@test/fixtures/bulkEmail';
import { makeTemplate } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { tableHeaders } from '@test/table';
import { server } from '@test/server';
import type { EmailTemplate } from '@/portal/api/types';
import { TemplatesPage } from './TemplatesPage';

/** The templates the fake server holds, and the bodies it was sent. */
interface TemplateServer {
  rows: EmailTemplate[];
  posted: unknown[];
  patched: unknown[];
  deleted: number[];
}

/** Answer the template endpoints from `rows`, recording each write. */
function answerTemplates(rows: EmailTemplate[]): TemplateServer {
  const state: TemplateServer = { rows, posted: [], patched: [], deleted: [] };
  server.use(
    http.get(`${API}/bulk-email/fields`, () => HttpResponse.json(FIELDS)),
    http.get(`${API}/bulk-email/templates`, () => HttpResponse.json(state.rows)),
    http.post(`${API}/bulk-email/templates`, async ({ request }) => {
      const body = (await request.json()) as Partial<EmailTemplate>;
      state.posted.push(body);
      if (body.name === 'Monthly newsletter') {
        return HttpResponse.json(
          { name: ['A template named "Monthly newsletter" already exists. Choose another name.'] },
          { status: 400 },
        );
      }
      const saved = makeTemplate({ ...body, id: 9 });
      state.rows = [...state.rows, saved];
      return HttpResponse.json(saved, { status: 201 });
    }),
    http.patch(`${API}/bulk-email/templates/:id`, async ({ params, request }) => {
      const body = (await request.json()) as Partial<EmailTemplate>;
      state.patched.push(body);
      const saved = makeTemplate({ ...body, id: Number(params.id) });
      state.rows = state.rows.map((row) => (row.id === saved.id ? saved : row));
      return HttpResponse.json(saved);
    }),
    http.delete(`${API}/bulk-email/templates/:id`, ({ params }) => {
      state.deleted.push(Number(params.id));
      state.rows = state.rows.filter((row) => row.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return state;
}

describe('TemplatesPage', () => {
  let state: TemplateServer;
  beforeEach(() => {
    state = answerTemplates([makeTemplate()]);
  });

  it('lists each template with its type and when it was last edited', async () => {
    renderWithProviders(<TemplatesPage />);
    const row = (await screen.findByRole('link', { name: 'Edit Monthly newsletter' })).closest(
      'tr',
    );
    await within(row as HTMLElement).findByText('First name');
    expect(
      within(row as HTMLElement)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual(expect.arrayContaining(['News for First name', 'Operational', '04/05/2026']));
  });

  it("shows a field in a template's subject as a chip", async () => {
    renderWithProviders(<TemplatesPage />);
    const chip = await screen.findByText('First name');
    expect(chip).toHaveClass('field-chip');
  });

  it('says so when there is no template yet', async () => {
    state.rows = [];
    renderWithProviders(<TemplatesPage />);
    expect(await screen.findByText('No templates yet')).toBeVisible();
  });

  it('saves a new template with its name, type, and subject', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Meeting notice');
    await user.click(screen.getByRole('radio', { name: 'Operational' }));
    await user.type(screen.getByRole('textbox', { name: /^Subject/ }), 'Meeting on Saturday');
    await user.click(screen.getByRole('button', { name: 'Add template' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Meeting notice saved.');
    expect(state.posted).toEqual([
      expect.objectContaining({
        name: 'Meeting notice',
        subject: 'Meeting on Saturday',
        email_type: 1,
        reply_to: '',
      }),
    ]);
  });

  it('shows a taken name beside the name', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Monthly newsletter');
    await user.click(screen.getByRole('button', { name: 'Add template' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A template named "Monthly newsletter" already exists. Choose another name.',
    );
  });

  it('refuses a template with no name, focusing the Name box, before asking the server', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    await user.click(screen.getByRole('button', { name: 'Add template' }));

    expect(screen.getByRole('textbox', { name: /^Name/ })).toHaveFocus();
    expect(state.posted).toEqual([]);
  });

  it('says beside Add template what to fix after a refused save', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    await user.click(screen.getByRole('button', { name: 'Add template' }));

    expect(await screen.findByText('Check the highlighted field.')).toBeInTheDocument();
  });

  it('moves the focus to the name the server refused', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Monthly newsletter');
    await user.click(screen.getByRole('button', { name: 'Add template' }));

    await screen.findByRole('alert');
    expect(screen.getByRole('textbox', { name: /^Name/ })).toHaveFocus();
  });

  it('renames a template from its Edit form', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('link', { name: 'Edit Monthly newsletter' }));
    const name = screen.getByRole('textbox', { name: /^Name/ });
    await user.clear(name);
    await user.type(name, 'Spring newsletter');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Spring newsletter saved.');
    expect(state.patched).toEqual([expect.objectContaining({ name: 'Spring newsletter' })]);
  });

  it('puts the name, which opens the edit, first and the trashcan last', async () => {
    renderWithProviders(<TemplatesPage />);
    const headers = tableHeaders(await screen.findByRole('table'));
    expect([headers[0], headers.at(-1)]).toEqual(['Name', 'Actions']);
  });

  it('offers the type as the compose screen does, each with what it is for', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    const types = screen.getByRole('group', { name: 'Type of email' });
    expect(within(types).getByRole('radio', { name: 'Mission' })).toHaveAccessibleDescription(
      'Requests for pilots and aircraft.',
    );
  });

  it('names the default address under Reply-To, as the compose screen does', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    expect(
      await screen.findByText(
        'When someone replies to this email, the reply goes to this address. Leave it empty to use office@caldart.org.',
      ),
    ).toBeVisible();
  });

  it('moves the focus into the form, and back to New template on Cancel', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'New template' }));
    expect(screen.getByRole('textbox', { name: /^Name/ })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'New template' })).toHaveFocus();
  });

  it('closes the form on Escape and goes back to the name that opened it', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    const name = await screen.findByRole('link', { name: 'Edit Monthly newsletter' });
    await user.click(name);
    expect(screen.getByRole('textbox', { name: /^Name/ })).toHaveFocus();
    await user.keyboard('{Escape}');
    expect([screen.queryByRole('form', { name: 'Save changes' }), document.activeElement]).toEqual([
      null,
      screen.getByRole('link', { name: 'Edit Monthly newsletter' }),
    ]);
  });

  it('deletes a template only once the trashcan is confirmed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'Delete Monthly newsletter' }));
    expect(state.deleted).toEqual([]);
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Monthly newsletter deleted.');
    expect(state.deleted).toEqual([3]);
  });
});
