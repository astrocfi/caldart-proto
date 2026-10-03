import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { makeGroup } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import type { RecipientGroup } from '@/portal/api/types';
import { GroupsPage } from './GroupsPage';

/** The groups the fake server holds, and the bodies it was sent. */
interface GroupServer {
  rows: RecipientGroup[];
  posted: unknown[];
  deleted: number[];
}

/** Answer the group list endpoints from `rows`, recording each write. */
function answerGroups(rows: RecipientGroup[]): GroupServer {
  const state: GroupServer = { rows, posted: [], deleted: [] };
  server.use(
    http.get(`${API}/bulk-email/groups`, () => HttpResponse.json(state.rows)),
    http.post(`${API}/bulk-email/groups`, async ({ request }) => {
      const body = (await request.json()) as Partial<RecipientGroup>;
      state.posted.push(body);
      return HttpResponse.json(makeGroup({ ...body, id: 9, count: 0 }), { status: 201 });
    }),
    http.delete(`${API}/bulk-email/groups/:id`, ({ params }) => {
      state.deleted.push(Number(params.id));
      state.rows = state.rows.filter((row) => row.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return state;
}

/** The groups screen, with a stand-in for a group's own page. */
function renderGroups(): ReturnType<typeof renderRoutes> {
  return renderRoutes(
    [
      { path: '/bulk-email/groups', element: <GroupsPage /> },
      { path: '/bulk-email/groups/:id', element: <p>The group page</p> },
    ],
    { route: '/bulk-email/groups' },
  );
}

describe('GroupsPage', () => {
  let state: GroupServer;
  beforeEach(() => {
    state = answerGroups([
      makeGroup(),
      makeGroup({ id: 6, name: 'Marin friends', kind: 'live', count: 41 }),
    ]);
  });

  it('lists each group with its kind and how many it holds now', async () => {
    renderGroups();
    const row = (await screen.findByRole('link', { name: 'Marin friends' })).closest('tr');
    expect(
      within(row as HTMLElement)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual(expect.arrayContaining(['Live', '41', '04/05/2026']));
  });

  it('links each group to its own page', async () => {
    renderGroups();
    expect(await screen.findByRole('link', { name: 'Board' })).toHaveAttribute(
      'href',
      '/bulk-email/groups/5',
    );
  });

  it("offers each group's people as a download", async () => {
    renderGroups();
    expect(
      await screen.findByRole('link', { name: 'Download the people in Board' }),
    ).toHaveAttribute('href', '/api/v1/bulk-email/groups/5/members.csv');
  });

  it('says what a fixed and a live group keep', async () => {
    renderGroups();
    expect(
      await screen.findByText('The same people every time, until you add or remove someone.'),
    ).toBeVisible();
  });

  it('makes a new group and opens its page', async () => {
    const user = userEvent.setup();
    const { router } = renderGroups();
    await user.click(await screen.findByRole('button', { name: 'New group' }));
    await user.type(screen.getByRole('textbox', { name: /^Name/ }), 'Seminar');
    await user.click(screen.getByRole('radio', { name: 'Live' }));
    await user.click(screen.getByRole('button', { name: 'Make the group' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bulk-email/groups/9'));
    expect(state.posted).toEqual([{ name: 'Seminar', kind: 'live' }]);
  });

  it('deletes a group only once the trashcan is confirmed', async () => {
    const user = userEvent.setup();
    renderGroups();
    await user.click(await screen.findByRole('button', { name: 'Delete Board' }));
    expect(state.deleted).toEqual([]);
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Board deleted.');
    expect(state.deleted).toEqual([5]);
  });
});
