import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeGroup, makeGroupPerson } from '@test/fixtures/bulkEmailReuse';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { headerWords } from '@test/table';
import type { GroupPerson, RecipientGroup } from '@/portal/api/types';
import { GroupDetailPage } from './GroupDetailPage';

/** What the fake server was asked to do to the group. */
interface GroupCalls {
  renamed: unknown[];
  added: unknown[];
  removed: number[];
  filtersAdded: unknown[];
  filtersRemoved: number[];
}

/** Answer one group's endpoints, with `people` in it now, recording each write. */
function answerGroup(group: RecipientGroup, people: GroupPerson[]): GroupCalls {
  const calls: GroupCalls = {
    renamed: [],
    added: [],
    removed: [],
    filtersAdded: [],
    filtersRemoved: [],
  };
  const base = `${API}/bulk-email/groups/${group.id}`;
  server.use(
    http.get(`${API}/darts`, () => HttpResponse.json([])),
    http.get(base, () => HttpResponse.json(group)),
    http.patch(base, async ({ request }) => {
      const body = (await request.json()) as Partial<RecipientGroup>;
      calls.renamed.push(body);
      return HttpResponse.json({ ...group, ...body });
    }),
    http.get(`${base}/members`, () => HttpResponse.json({ count: people.length, people })),
    http.post(`${base}/members`, async ({ request }) => {
      calls.added.push(await request.json());
      return HttpResponse.json(makeGroupPerson({ user_id: 30, name: 'Cal Cole' }), {
        status: 201,
      });
    }),
    http.delete(`${base}/members/:user`, ({ params }) => {
      calls.removed.push(Number(params.user));
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(`${base}/filters`, async ({ request }) => {
      calls.filtersAdded.push(await request.json());
      return HttpResponse.json(
        { id: 9, label: 'Everybody', filters: {}, position: 1 },
        { status: 201 },
      );
    }),
    http.delete(`${base}/filters/:fid`, ({ params }) => {
      calls.filtersRemoved.push(Number(params.fid));
      return new HttpResponse(null, { status: 204 });
    }),
    http.get(`${API}/bulk-email/groups/people`, () =>
      HttpResponse.json([{ id: 30, name: 'Cal Cole', email: 'cal@example.org' }]),
    ),
  );
  return calls;
}

/** The page of group `id`. */
function renderGroup(id: number): void {
  renderRoutes([{ path: '/bulk-email/groups/:id', element: <GroupDetailPage /> }], {
    route: `/bulk-email/groups/${id}`,
  });
}

const MARIN = makeGroup({
  id: 6,
  name: 'Marin friends',
  kind: 'live',
  count: 1,
  filter_sets: [
    {
      id: 8,
      label: 'Kind: Friends only, County: Marin',
      filters: { kind: 'friend', county: 'Marin' },
      position: 0,
      needs_fixing: false,
    },
  ],
});

describe('GroupDetailPage, a fixed group', () => {
  it('lists its people with their DART', async () => {
    answerGroup(makeGroup(), [makeGroupPerson()]);
    renderGroup(5);
    const row = (await screen.findByRole('rowheader', { name: 'Ann Able' })).closest('tr');
    expect(row).toHaveTextContent('Marin DART');
  });

  it('marks a deactivated person', async () => {
    answerGroup(makeGroup(), [makeGroupPerson({ is_active: false })]);
    renderGroup(5);
    expect(await screen.findByRole('rowheader', { name: 'Ann Able (deactivated)' })).toBeVisible();
  });

  it('adds the person picked from the search', async () => {
    const calls = answerGroup(makeGroup(), [makeGroupPerson()]);
    const user = userEvent.setup();
    renderGroup(5);
    await user.type(await screen.findByRole('combobox', { name: /Add a person/ }), 'Cole');
    await user.click(await screen.findByRole('option', { name: /Cal Cole/ }));
    expect(await screen.findByText('Cal Cole added.')).toBeVisible();
    expect(calls.added).toEqual([{ user: 30 }]);
  });

  it('removes a person only once the trashcan is confirmed', async () => {
    const calls = answerGroup(makeGroup(), [makeGroupPerson()]);
    const user = userEvent.setup();
    renderGroup(5);
    await user.click(await screen.findByRole('button', { name: 'Remove Ann Able from the group' }));
    expect(calls.removed).toEqual([]);
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(calls.removed).toEqual([12]));
  });

  it('renames the group', async () => {
    const calls = answerGroup(makeGroup(), []);
    const user = userEvent.setup();
    renderGroup(5);
    const name = await screen.findByRole('textbox', { name: /Group name/ });
    await user.clear(name);
    await user.type(name, 'Directors');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(calls.renamed).toEqual([{ name: 'Directors' }]));
  });

  it('puts the name first and the trashcan last, where every table keeps its actions', async () => {
    answerGroup(makeGroup(), [makeGroupPerson()]);
    renderGroup(5);
    await screen.findByRole('rowheader', { name: 'Ann Able' });
    const headers = screen.getAllByRole('columnheader').map(headerWords);
    expect([headers[0], headers.at(-1)]).toEqual(['Name', 'Remove']);
  });

  it('has no filters to change', async () => {
    answerGroup(makeGroup(), []);
    renderGroup(5);
    await screen.findByRole('heading', { name: 'People' });
    expect(screen.queryByRole('button', { name: 'Add these filters' })).toBeNull();
  });
});

describe('GroupDetailPage, a live group', () => {
  it('lists its filters in words', async () => {
    answerGroup(MARIN, [makeGroupPerson()]);
    renderGroup(6);
    expect(await screen.findByText('Kind: Friends only, County: Marin')).toBeVisible();
  });

  it('adds the filters chosen in the bar', async () => {
    const calls = answerGroup(MARIN, [makeGroupPerson()]);
    const user = userEvent.setup();
    renderGroup(6);
    await user.click(await screen.findByRole('button', { name: 'Add these filters' }));
    await waitFor(() => expect(calls.filtersAdded).toEqual([{ filters: {} }]));
  });

  it('says what it added and empties the bar', async () => {
    answerGroup(MARIN, [makeGroupPerson()]);
    const user = userEvent.setup();
    renderGroup(6);
    const filters = await screen.findByRole('search', { name: 'Choose filters to add' });
    await user.type(within(filters).getByRole('searchbox', { name: /Search/ }), 'Able');
    await user.click(screen.getByRole('button', { name: 'Add these filters' }));
    expect(await screen.findByText('Added the filters Everybody.')).toBeVisible();
    expect(
      within(screen.getByRole('search', { name: 'Choose filters to add' })).getByRole('searchbox', {
        name: /Search/,
      }),
    ).toHaveValue('');
  });

  it('marks a filter set the member list no longer accepts', async () => {
    const broken = makeGroup({
      ...MARIN,
      count: null,
      needs_fixing: true,
      filter_sets: [
        { id: 8, label: 'DART: 99', filters: { dart: '99' }, position: 0, needs_fixing: true },
      ],
    });
    answerGroup(broken, []);
    server.use(
      http.get(`${API}/bulk-email/groups/6/members`, () =>
        HttpResponse.json({ detail: "This group's filters need fixing." }, { status: 409 }),
      ),
    );
    renderGroup(6);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "This group's filters need fixing. The member list no longer accepts these filters",
    );
  });

  it('takes a filter set out only once the trashcan is confirmed', async () => {
    const calls = answerGroup(MARIN, []);
    const user = userEvent.setup();
    renderGroup(6);
    await user.click(
      await screen.findByRole('button', {
        name: 'Remove the filters Kind: Friends only, County: Marin',
      }),
    );
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(calls.filtersRemoved).toEqual([8]));
  });

  it('offers the list as a download while it finds somebody', async () => {
    answerGroup(MARIN, [makeGroupPerson()]);
    renderGroup(6);
    expect(await screen.findByRole('link', { name: 'Download list' })).toHaveAttribute(
      'href',
      '/api/v1/bulk-email/groups/6/members.csv',
    );
  });

  it('offers no download while its filters find nobody', async () => {
    answerGroup({ ...MARIN, count: 0, filter_sets: [] }, []);
    renderGroup(6);
    await screen.findByRole('heading', { name: 'Who it finds now' });
    await screen.findByText('Nobody is in this group');
    expect(screen.queryByRole('link', { name: 'Download list' })).toBeNull();
  });

  it('lists whoever its filters find now, with no way to add one person', async () => {
    answerGroup(MARIN, [makeGroupPerson()]);
    renderGroup(6);
    expect(await screen.findByRole('heading', { name: 'Who it finds now' })).toBeVisible();
    expect(screen.queryByRole('combobox', { name: /Add a person/ })).toBeNull();
  });
});
