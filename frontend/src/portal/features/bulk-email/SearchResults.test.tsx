import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import {
  answerBulkEmail,
  makeBatch,
  makeBulkEmail,
  makeMatch,
  makeMatches,
  makeRow,
} from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { ComposePage } from './ComposePage';
import { matchSentence } from './SearchResults';

/** Render the compose screen of the email in `state`. */
function renderCompose(state: BulkEmailState): void {
  renderRoutes([{ path: '/bulk-email/compose/:id', element: <ComposePage /> }], {
    route: `/bulk-email/compose/${state.email.id}`,
  });
}

/** A draft whose batch holds Ann Able, whose search matches Bea Bell. */
function draftState(): BulkEmailState {
  return { email: makeBulkEmail(), batch: makeBatch([makeRow()]) };
}

/** The table of the people the search matches. */
async function matchesTable(): Promise<HTMLElement> {
  return screen.findByRole('table', { name: /^People these filters match/ });
}

describe('the search on Who gets it', () => {
  it('shows the people the filters match before anybody is added', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    expect(within(await matchesTable()).getByText('Bea Bell')).toBeVisible();
    expect(calls.adds).toEqual([]);
  });

  it('says whether each matched person would receive the email', async () => {
    const state = draftState();
    state.matches = makeMatches([
      makeMatch({ will_receive: false, reason: 'Account deactivated' }),
    ]);
    answerBulkEmail(state);
    renderCompose(state);
    expect(within(await matchesTable()).getByText('Account deactivated')).toBeVisible();
  });

  it('searches again with the filters chosen', async () => {
    const calls = answerBulkEmail(draftState());
    const user = userEvent.setup();
    renderCompose(draftState());
    const filters = await screen.findByRole('search', { name: 'Choose people to add' });
    await user.selectOptions(within(filters).getByLabelText('Kind'), 'friend');
    await waitFor(() => expect(calls.searches.at(-1)).toBe('kind=friend&page=1&page_size=10'));
  });

  it('adds the people shown when Add these people is pressed', async () => {
    const calls = answerBulkEmail(draftState());
    const user = userEvent.setup();
    renderCompose(draftState());
    const filters = await screen.findByRole('search', { name: 'Choose people to add' });
    await user.selectOptions(within(filters).getByLabelText('Kind'), 'friend');
    await screen.findByText('1 person matches these filters.');
    await user.click(screen.getByRole('button', { name: 'Add these people' }));
    await screen.findByText(/^Added 1 person/);
    expect(calls.adds).toEqual([{ filters: { kind: 'friend' } }]);
  });

  it('offers no add while nobody matches', async () => {
    const state = draftState();
    state.matches = makeMatches([]);
    answerBulkEmail(state);
    renderCompose(state);
    await screen.findByText('Nobody matches these filters.');
    expect(screen.getByRole('button', { name: 'Add these people' })).toBeDisabled();
  });

  it('pages through a long search ten at a time', async () => {
    const state = draftState();
    state.matches = makeMatches(
      Array.from({ length: 10 }, (_, index) =>
        makeMatch({ user_id: index + 1, name: `Person ${index + 1}` }),
      ),
      12,
    );
    const calls = answerBulkEmail(state);
    const user = userEvent.setup();
    renderCompose(state);
    await screen.findByText('With no filters chosen, this is every member and friend: 12 people.');
    const pages = screen.getByRole('navigation', { name: 'Pages of matching people' });
    await user.click(within(pages).getByRole('button', { name: /Next/ }));
    await waitFor(() => expect(calls.searches.at(-1)).toBe('page=2&page_size=10'));
  });

  it('takes several DARTs in the DART filter', async () => {
    const calls = answerBulkEmail(draftState());
    server.use(
      http.get(`${API}/darts`, () =>
        HttpResponse.json([
          { id: 1, name: 'Marin' },
          { id: 2, name: 'Napa' },
          { id: 3, name: 'Solano' },
        ]),
      ),
    );
    const user = userEvent.setup();
    renderCompose(draftState());
    await screen.findByRole('search', { name: 'Choose people to add' });
    await user.click(screen.getByLabelText('DART'));
    await user.click(await screen.findByRole('checkbox', { name: 'Marin' }));
    await user.click(screen.getByRole('checkbox', { name: 'Solano' }));
    await waitFor(() => expect(calls.searches.at(-1)).toBe('dart=1%2C3&page=1&page_size=10'));
  });
});

describe('matchSentence', () => {
  it('names the DART a leader is held to when no filter is chosen', () => {
    expect(matchSentence(3, true, 'Marin')).toBe(
      'With no filters chosen, this is every member and friend of the Marin DART: 3 people.',
    );
  });

  it('counts the people a filtered search matches', () => {
    expect(matchSentence(2, false, '')).toBe('2 people match these filters.');
  });
});
