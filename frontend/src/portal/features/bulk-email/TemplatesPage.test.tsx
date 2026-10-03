import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { FIELDS } from '@test/fixtures/bulkEmail';
import { makeTemplate } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
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
    const row = (await screen.findByRole('cell', { name: 'Monthly newsletter' })).closest('tr');
    expect(
      within(row as HTMLElement)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual(expect.arrayContaining(['News for {first_name}', 'Operational', '04/05/2026']));
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
    await user.selectOptions(screen.getByRole('combobox', { name: /Type of email/ }), '1');
    await user.type(screen.getByRole('textbox', { name: /^Subject/ }), 'Meeting on Saturday');
    await user.click(screen.getByRole('button', { name: 'Save template' }));
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
    await user.click(screen.getByRole('button', { name: 'Save template' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A template named "Monthly newsletter" already exists. Choose another name.',
    );
  });

  it('renames a template from its Edit form', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TemplatesPage />);
    await user.click(await screen.findByRole('button', { name: 'Edit Monthly newsletter' }));
    const name = screen.getByRole('textbox', { name: /^Name/ });
    await user.clear(name);
    await user.type(name, 'Spring newsletter');
    await user.click(screen.getByRole('button', { name: 'Save template' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Spring newsletter saved.');
    expect(state.patched).toEqual([expect.objectContaining({ name: 'Spring newsletter' })]);
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
