import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { FIELDS, answerBulkEmail, makeBatch, makeBulkEmail } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { makeTemplate } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderRoutes, signedInClient } from '@test/render';
import { server } from '@test/server';
import { ComposePage } from './ComposePage';
import { TYPE_CHANGED_MESSAGE } from './EmailTypeChoice';

/**
 * A scheduled email, served so that a change of type, by hand or by a template, takes
 * it back to the drafts as the server does.
 */
function scheduled(): BulkEmailState {
  const state: BulkEmailState = {
    email: makeBulkEmail({
      status: 'queued',
      scheduled: true,
      start_at: '2027-01-04T16:00:00Z',
      can_edit: true,
    }),
    batch: makeBatch([]),
  };
  answerBulkEmail(state);
  server.use(
    http.get(`${API}/bulk-email/fields`, () => HttpResponse.json(FIELDS)),
    http.patch(`${API}/bulk-email/7`, async ({ request }) => {
      const patch = (await request.json()) as { email_type?: number };
      state.email = { ...state.email, ...patch, status: 'draft', start_at: null };
      return HttpResponse.json(state.email);
    }),
    http.get(`${API}/bulk-email/templates`, () =>
      HttpResponse.json([makeTemplate({ email_type: 2, email_type_name: 'Mission' })]),
    ),
    http.post(`${API}/bulk-email/7/apply-template`, () => {
      state.email = { ...state.email, email_type: 2, status: 'draft', start_at: null };
      return HttpResponse.json(state.email);
    }),
  );
  return state;
}

/** The compose screen of email 7 for CalDART management. */
function renderCompose(): void {
  renderRoutes([{ path: '/bulk-email/compose/:id', element: <ComposePage /> }], {
    route: '/bulk-email/compose/7',
    client: signedInClient('management'),
  });
}

describe('a change of type on a scheduled email', () => {
  it('says the email is back in the drafts when the type is chosen by hand', async () => {
    scheduled();
    const user = userEvent.setup();
    renderCompose();
    const radios = await screen.findAllByRole('radio');
    const other = radios.find((radio) => !(radio as HTMLInputElement).checked);
    await user.click(other as HTMLElement);
    expect(await screen.findByText(TYPE_CHANGED_MESSAGE)).toBeVisible();
  });

  it('says the email is back in the drafts when a template changes the type', async () => {
    scheduled();
    const user = userEvent.setup();
    renderCompose();
    await user.click(await screen.findByRole('button', { name: 'Start from a template' }));
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Template' }), '3');
    await user.click(screen.getByRole('button', { name: 'Use this template' }));
    await user.click(screen.getByRole('button', { name: 'Replace my words' }));
    expect(await screen.findByText(TYPE_CHANGED_MESSAGE)).toBeVisible();
  });
});
