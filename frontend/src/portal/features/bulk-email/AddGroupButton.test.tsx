import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import {
  FIELDS,
  answerBulkEmail,
  makeBatch,
  makeBulkEmail,
  makeRow,
} from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { makeGroup } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderRoutes, signedInClient } from '@test/render';
import { server } from '@test/server';
import type { RoleSlug } from '@/portal/api/types';
import { ComposePage } from './ComposePage';

/** What the fake server was asked to do with groups. */
interface GroupCalls {
  added: unknown[];
  saved: unknown[];
}

/** Answer the compose screen of `state`'s email and the group endpoints it calls. */
function answerCompose(state: BulkEmailState): GroupCalls {
  answerBulkEmail(state);
  const calls: GroupCalls = { added: [], saved: [] };
  const base = `${API}/bulk-email/${state.email.id}`;
  server.use(
    http.get(`${API}/bulk-email/fields`, () => HttpResponse.json(FIELDS)),
    http.get(`${API}/bulk-email/groups`, () =>
      HttpResponse.json([makeGroup(), makeGroup({ id: 6, name: 'Marin friends', kind: 'live' })]),
    ),
    http.post(`${base}/batch/add-group`, async ({ request }) => {
      calls.added.push(await request.json());
      return HttpResponse.json({ added: 1, already_present: 1, count: 2 });
    }),
    http.post(`${base}/save-group`, async ({ request }) => {
      const body = (await request.json()) as { name: string };
      calls.saved.push(body);
      if (body.name === 'Board') {
        return HttpResponse.json(
          { name: ['A group named "Board" already exists. Choose another name.'] },
          { status: 400 },
        );
      }
      return HttpResponse.json(makeGroup({ ...body, id: 9 }), { status: 201 });
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

/** A draft whose batch holds Ann Able. */
function draft(): BulkEmailState {
  return { email: makeBulkEmail(), batch: makeBatch([makeRow()]) };
}

describe('Add a saved group', () => {
  it('lists each group with its kind and size', async () => {
    const state = draft();
    answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await user.click(await screen.findByRole('button', { name: 'Add a saved group' }));
    expect(
      await screen.findByRole('button', { name: 'Marin friends: live, 2 people' }),
    ).toBeVisible();
  });

  it('adds the group chosen and says what the add did', async () => {
    const state = draft();
    const calls = answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await user.click(await screen.findByRole('button', { name: 'Add a saved group' }));
    await user.click(await screen.findByRole('button', { name: 'Board: fixed, 2 people' }));
    expect(await screen.findByText('Added 1 person; 1 was already in the batch.')).toBeVisible();
    expect(calls.added).toEqual([{ group: 5 }]);
  });

  it('is not offered to somebody outside CalDART management', async () => {
    const state = draft();
    answerCompose(state);
    renderCompose(state, 'dart_leader');
    await screen.findByRole('button', { name: 'Add to batch' });
    expect(screen.queryByRole('button', { name: 'Add a saved group' })).toBeNull();
  });
});

describe('Save as a group', () => {
  it('saves the batch under the name and kind given, then links the group', async () => {
    const state = draft();
    const calls = answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await user.click(await screen.findByRole('button', { name: 'Save as a group' }));
    const form = screen.getByRole('form', { name: 'Save the batch as a group' });
    await user.type(within(form).getByRole('textbox', { name: /Group name/ }), 'Hangar crew');
    await user.click(within(form).getByRole('radio', { name: 'Live' }));
    await user.click(within(form).getByRole('button', { name: 'Save group' }));
    expect(await screen.findByRole('link', { name: 'Hangar crew' })).toHaveAttribute(
      'href',
      '/bulk-email/groups/9',
    );
    expect(calls.saved).toEqual([{ name: 'Hangar crew', kind: 'live' }]);
  });

  it('shows a taken name beside the name', async () => {
    const state = draft();
    answerCompose(state);
    const user = userEvent.setup();
    renderCompose(state, 'management');
    await user.click(await screen.findByRole('button', { name: 'Save as a group' }));
    const form = screen.getByRole('form', { name: 'Save the batch as a group' });
    await user.type(within(form).getByRole('textbox', { name: /Group name/ }), 'Board');
    await user.click(within(form).getByRole('button', { name: 'Save group' }));
    await waitFor(() =>
      expect(within(form).getByRole('alert')).toHaveTextContent(
        'A group named "Board" already exists. Choose another name.',
      ),
    );
  });

  it('is not offered for an empty batch', async () => {
    const state: BulkEmailState = { email: makeBulkEmail(), batch: makeBatch([]) };
    answerCompose(state);
    renderCompose(state, 'management');
    await screen.findByText('Nobody is in the batch yet');
    expect(screen.queryByRole('button', { name: 'Save as a group' })).toBeNull();
  });
});
