import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { FIELDS, answerBulkEmail, makeBatch, makeBulkEmail } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { makeTemplate } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderRoutes, signedInClient } from '@test/render';
import { server } from '@test/server';
import type { RoleSlug } from '@/portal/api/types';
import { ComposePage } from './ComposePage';
import { hasWords, REPLACE_WARNING } from './StartFromTemplate';

/** What the fake server was asked to do with templates. */
interface TemplateCalls {
  applied: unknown[];
  saved: unknown[];
}

/**
 * Answer the compose screen of `state`'s email, the template list, and the template
 * endpoints: applying the template fills the email with its words.
 */
function answerCompose(state: BulkEmailState): TemplateCalls {
  answerBulkEmail(state);
  const calls: TemplateCalls = { applied: [], saved: [] };
  const template = makeTemplate();
  server.use(
    http.get(`${API}/bulk-email/fields`, () => HttpResponse.json(FIELDS)),
    http.get(`${API}/bulk-email/templates`, () => HttpResponse.json([template])),
    http.post(`${API}/bulk-email/templates`, async ({ request }) => {
      const body = (await request.json()) as { name: string };
      calls.saved.push(body);
      return HttpResponse.json(makeTemplate({ ...body, id: 9 }), { status: 201 });
    }),
    http.post(`${API}/bulk-email/${state.email.id}/apply-template`, async ({ request }) => {
      calls.applied.push(await request.json());
      state.email = { ...state.email, subject: template.subject, body: template.body };
      return HttpResponse.json(state.email);
    }),
  );
  return calls;
}

/** Render the compose screen of `state`'s email for somebody with `roles`. */
function renderCompose(state: BulkEmailState, ...roles: RoleSlug[]): void {
  renderRoutes([{ path: '/bulk-email/compose/:id', element: <ComposePage /> }], {
    route: `/bulk-email/compose/${state.email.id}`,
    client: signedInClient(...roles),
  });
}

/** An email with nothing written yet. */
function emptyDraft(): BulkEmailState {
  return { email: makeBulkEmail({ subject: '', body: '' }), batch: makeBatch([]) };
}

/** Open Start from a template and choose the monthly newsletter. */
async function chooseNewsletter(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole('button', { name: 'Start from a template' }));
  await user.selectOptions(await screen.findByRole('combobox', { name: 'Template' }), '3');
}

describe('hasWords', () => {
  it.each([
    ['', '', false],
    ['', '<p></p>', false],
    ['Hi', '', true],
    ['', '<p>Hello</p>', true],
    ['', '<p><img src="https://e.org/a.png" alt="Hangar"></p>', true],
  ])('reads subject %j and message %j as %s', (subject, body, expected) => {
    expect(hasWords(subject, body)).toBe(expected);
  });
});

describe('Start from a template', () => {
  it('fills an empty draft at once and shows the template words', async () => {
    const state = emptyDraft();
    const calls = answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await chooseNewsletter(user);
    await user.click(screen.getByRole('button', { name: 'Use this template' }));
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: /^Subject/ })).toHaveValue(
        'News for {first_name}',
      ),
    );
    expect(calls.applied).toEqual([{ template: 3 }]);
  });

  it('asks before it replaces words already written', async () => {
    const state: BulkEmailState = { email: makeBulkEmail(), batch: makeBatch([]) };
    const calls = answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await chooseNewsletter(user);
    await user.click(screen.getByRole('button', { name: 'Use this template' }));
    expect(screen.getByText(REPLACE_WARNING)).toBeVisible();
    expect(calls.applied).toEqual([]);
    await user.click(screen.getByRole('button', { name: 'Replace my words' }));
    await waitFor(() => expect(calls.applied).toEqual([{ template: 3 }]));
  });

  it('keeps the words when the question is answered Cancel', async () => {
    const state: BulkEmailState = { email: makeBulkEmail(), batch: makeBatch([]) };
    const calls = answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await chooseNewsletter(user);
    await user.click(screen.getByRole('button', { name: 'Use this template' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect([calls.applied, screen.getByRole('textbox', { name: /^Subject/ })]).toEqual([
      [],
      expect.objectContaining({ value: 'Hangar day' }),
    ]);
  });

  it('saves the draft words and Reply-To as a template under the name given', async () => {
    const state: BulkEmailState = {
      email: makeBulkEmail({ reply_to: 'hangar@example.org' }),
      batch: makeBatch([]),
    };
    const calls = answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await user.click(await screen.findByRole('button', { name: 'Save as a template' }));
    const form = screen.getByRole('form', { name: 'Save as a template' });
    await user.type(within(form).getByRole('textbox', { name: /Template name/ }), 'Hangar');
    await user.click(within(form).getByRole('button', { name: 'Save template' }));
    expect(await screen.findByText(/Saved as the template Hangar\./)).toBeVisible();
    expect(screen.getByRole('link', { name: 'Templates' })).toHaveAttribute(
      'href',
      '/bulk-email/templates',
    );
    expect(calls.saved).toEqual([
      {
        name: 'Hangar',
        subject: 'Hangar day',
        body: '<p>Bring gloves.</p>',
        email_type: 1,
        reply_to: 'hangar@example.org',
      },
    ]);
  });

  it('is not offered to somebody outside CalDART management', async () => {
    const state = emptyDraft();
    answerCompose(state);
    renderCompose(state, 'dart_leader');
    await screen.findByRole('heading', { name: '2. What it says' });
    expect(screen.queryByRole('button', { name: 'Start from a template' })).toBeNull();
  });
});
