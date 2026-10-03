import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { renderRoutes } from '@test/render';
import { ComposePage } from './ComposePage';
import { BACK_TO_DRAFT_MESSAGE, SHORT_LIST_LENGTH } from './RecipientsCard';
import { AUTOSAVE_MS } from './useAutosave';

/** Render the compose screen of the email in `state`. */
function renderCompose(state: BulkEmailState) {
  return renderRoutes([{ path: '/bulk-email/compose/:id', element: <ComposePage /> }], {
    route: `/bulk-email/compose/${state.email.id}`,
  });
}

/** A draft whose batch holds Ann Able alone. */
function draftState(overrides: Partial<BulkEmailState['email']> = {}): BulkEmailState {
  return { email: makeBulkEmail(overrides), batch: makeBatch([makeRow()]) };
}

/** A user-event session that moves the fake clock along with its own waits. */
function typist() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

/** Let the clock run `ms` and every request and promise it set going settle. */
async function pass(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ComposePage', () => {
  it('reads as three numbered cards', async () => {
    answerBulkEmail(draftState());
    renderCompose(draftState());
    await screen.findByRole('heading', { name: '1. Who gets it' });
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      '1. Who gets it',
      '2. What it says',
      '3. Check and send',
    ]);
  });

  it('asks for the type at the top of What it says', async () => {
    answerBulkEmail(draftState({ email_type: null, email_type_name: '' }));
    renderCompose(draftState({ email_type: null, email_type_name: '' }));
    const types = await screen.findByRole('group', { name: 'Type of email' });
    expect(within(types).getByRole('radio', { name: 'Operational' })).not.toBeChecked();
  });

  it('says why an email came back unsent', async () => {
    const reason = 'This email was not sent: you can no longer send Mission email.';
    answerBulkEmail(draftState({ not_sent_reason: reason }));
    renderCompose(draftState({ not_sent_reason: reason }));
    expect(await screen.findByText(reason)).toBeVisible();
  });

  it('explains the batch the first time it is named', async () => {
    answerBulkEmail(draftState());
    renderCompose(draftState());
    expect(
      await screen.findByText(
        /The people you add make up the batch: the list this email goes to\./,
      ),
    ).toBeVisible();
  });

  it('adds the filtered people to the batch, says how many joined, and keeps the focus', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    const user = typist();
    await user.click(await screen.findByRole('button', { name: 'Add to batch' }));
    await pass(500);
    expect(await screen.findByText('Added 1 person; 1 was already in the batch.')).toBeVisible();
    expect(calls.adds).toEqual([{ filters: {} }]);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Add to batch' })).toHaveFocus());
  });

  it('adds by a search typed just before the press', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    const user = typist();
    const filters = await screen.findByRole('search', { name: 'Choose people to add' });
    await user.type(within(filters).getByLabelText('Search'), 'bea');
    await user.click(screen.getByRole('button', { name: 'Add to batch' }));
    // In two steps, as real time passes: the bar's pause, then the add's.
    await pass(300);
    await pass(300);
    expect(calls.adds).toEqual([{ filters: { search: 'bea' } }]);
  });

  it('says a batch change took a scheduled email back to the drafts', async () => {
    const state = draftState({
      status: 'queued',
      scheduled: true,
      start_at: '2027-04-07T15:00:00Z',
    });
    answerBulkEmail(state);
    renderCompose(state);
    const user = typist();
    await user.click(await screen.findByRole('button', { name: 'Add to batch' }));
    await pass(500);
    expect(await screen.findByText(BACK_TO_DRAFT_MESSAGE)).toBeVisible();
  });

  it('counts who will receive the email and who is skipped', async () => {
    const state = draftState({ batch_count: 2, receiving_count: 1, batch_skipped_count: 1 });
    state.batch = makeBatch([
      makeRow(),
      makeRow({ id: 2, name: 'Gil Gone', will_receive: false, reason: 'Account deactivated' }),
    ]);
    answerBulkEmail(state);
    renderCompose(state);
    expect(
      await screen.findByText('1 person will receive this email; 1 is skipped.'),
    ).toBeVisible();
    expect(screen.getByText('Gil Gone').closest('tr')).toHaveTextContent('Account deactivated');
  });

  it('shows no count while the batch is empty', async () => {
    const state = draftState({ batch_count: 0, receiving_count: 0 });
    state.batch = makeBatch([]);
    answerBulkEmail(state);
    renderCompose(state);
    expect(await screen.findByText('Nobody is in the batch yet')).toBeVisible();
    expect(screen.queryByText(/will receive this email/)).toBeNull();
  });

  it('keeps the batch in the order the server gives, surname first', async () => {
    const state = draftState();
    state.batch = makeBatch([
      makeRow({ id: 1, name: 'Zed Abbott', email: 'zed@example.org' }),
      makeRow({ id: 2, name: 'Amy Young', email: 'amy@example.org' }),
    ]);
    answerBulkEmail(state);
    renderCompose(state);
    await screen.findByText('Zed Abbott');
    const names = screen
      .getAllByRole('row')
      .slice(1)
      .map((row) => row.firstChild?.textContent);
    expect(names).toEqual(['Zed Abbott', 'Amy Young']);
  });

  it('shows the first ten of a long batch until Show all is pressed', async () => {
    const state = draftState();
    state.batch = makeBatch(
      Array.from({ length: 12 }, (_, index) =>
        makeRow({ id: index + 1, name: `Person ${index + 1}`, email: `p${index}@example.org` }),
      ),
    );
    answerBulkEmail(state);
    renderCompose(state);
    const table = await screen.findByRole('table', { name: 'The batch: 12 people' });
    expect(within(table).getAllByRole('row')).toHaveLength(SHORT_LIST_LENGTH + 1);
    await typist().click(screen.getByRole('button', { name: 'Show all 12' }));
    expect(within(table).getAllByRole('row')).toHaveLength(13);
  });

  it('gives the name and the address a real width and starts the name at the left', async () => {
    answerBulkEmail(draftState());
    renderCompose(draftState());
    const table = await screen.findByRole('table', { name: 'The batch: 1 person' });
    const headers = within(table).getAllByRole('columnheader');
    expect(headers.map((header) => header.textContent)).toEqual([
      'Name',
      'Email',
      'Will receive?',
      'Remove',
      'Kind',
      'DART',
      'Chosen by',
    ]);
    expect(headers[0]).toHaveClass('data-table__text');
    expect(table.style.minWidth).toContain('16rem + 14rem');
  });

  it('takes one person out once the trashcan is confirmed', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    const user = typist();
    await user.click(await screen.findByRole('button', { name: 'Remove Ann Able from the batch' }));
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(calls.removed).toEqual([1]));
  });

  it('clears the batch only from its confirmation', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    const user = typist();
    await user.click(await screen.findByRole('button', { name: 'Clear batch' }));
    expect(calls.clears).toBe(0);
    await user.click(screen.getByRole('button', { name: 'Clear the batch' }));
    await waitFor(() => expect(calls.clears).toBe(1));
  });

  it('offers the batch as a download', async () => {
    answerBulkEmail(draftState());
    renderCompose(draftState());
    expect(await screen.findByRole('link', { name: 'Download list' })).toHaveAttribute(
      'href',
      '/api/v1/bulk-email/7/batch.csv',
    );
  });

  it('says nothing about saving on a draft nobody has touched', async () => {
    answerBulkEmail(draftState());
    renderCompose(draftState());
    await screen.findByRole('heading', { name: '2. What it says' });
    expect(screen.queryByText('Saved')).toBeNull();
  });

  it('saves the subject by itself once the typing pauses', async () => {
    const calls = answerBulkEmail(draftState({ subject: '' }));
    renderCompose(draftState({ subject: '' }));
    await typist().type(await screen.findByRole('textbox', { name: /^Subject/ }), 'Fly-in');
    await pass(AUTOSAVE_MS + 100);
    expect(calls.patches).toEqual([{ subject: 'Fly-in' }]);
    expect(await screen.findByText('Saved')).toBeVisible();
  });

  it('holds a sent email still, without the drafting instructions or the send card', async () => {
    const state = draftState({ status: 'sent', can_edit: false, sent_count: 1 });
    answerBulkEmail(state);
    renderCompose(state);
    const banner = await screen.findByRole('region', { name: 'Sent' });
    expect(within(banner).getByRole('link', { name: 'See who received it' })).toHaveAttribute(
      'href',
      '/bulk-email/sent/7',
    );
    expect(screen.getByRole('textbox', { name: /^Subject/ })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Add to batch' })).toBeNull();
    expect(screen.queryByRole('heading', { name: '3. Check and send' })).toBeNull();
    expect(screen.queryByText(/Your work saves itself/)).toBeNull();
  });

  it('shows the progress and Stop in the banner while sending', async () => {
    const state = draftState({
      status: 'sending',
      can_edit: false,
      started_at: '2026-04-06T17:00:00Z',
      sent_count: 12,
      remaining: 26,
      estimated_finish_at: new Date(Date.now() + 60_000).toISOString(),
    });
    answerBulkEmail(state);
    renderCompose(state);
    const banner = await screen.findByRole('region', { name: 'Sending' });
    expect(within(banner).getByText(/^Sending… 12 of 38 sent/)).toBeVisible();
    expect(within(banner).getByRole('button', { name: 'Stop sending' })).toBeVisible();
  });

  it('shows the countdown and Cancel once, in the banner', async () => {
    const state = draftState({
      status: 'queued',
      start_at: new Date(Date.now() + 60_000).toISOString(),
    });
    answerBulkEmail(state);
    renderCompose(state);
    const banner = await screen.findByRole('region', { name: 'Waiting to send' });
    expect(within(banner).getByText(/^Sending in /)).toBeVisible();
    expect(screen.getAllByRole('button', { name: 'Cancel' })).toHaveLength(1);
  });

  it('shows a scheduled email under a banner that can cancel the schedule', async () => {
    const state = draftState({
      status: 'queued',
      scheduled: true,
      start_at: '2026-10-04T15:00:00Z',
    });
    const calls = answerBulkEmail(state);
    renderCompose(state);
    const banner = await screen.findByRole('region', { name: 'Waiting to send' });
    expect(banner).toHaveTextContent('Scheduled for 10/04/2026 at 8:00 AM Pacific time.');
    await typist().click(within(banner).getByRole('button', { name: 'Cancel the schedule' }));
    await waitFor(() => expect(calls.actions).toEqual(['cancel']));
  });

  it('offers Stop rather than Cancel for an email waiting to send the rest', async () => {
    const state = draftState({
      status: 'queued',
      can_edit: false,
      started_at: '2026-04-06T17:00:00Z',
      start_at: '2026-04-06T17:05:00Z',
      remaining: 2,
    });
    answerBulkEmail(state);
    renderCompose(state);
    const banner = await screen.findByRole('region', { name: 'Waiting to send' });
    expect(banner).toHaveTextContent('Waiting to send the rest.');
    expect(within(banner).getByRole('button', { name: 'Stop sending' })).toBeVisible();
    expect(within(banner).queryByRole('button', { name: 'Cancel' })).toBeNull();
  });
});
