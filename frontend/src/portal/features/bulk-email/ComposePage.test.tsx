import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { renderRoutes } from '@test/render';
import { ComposePage } from './ComposePage';

/** Render the compose screen of the email in `state`. */
function renderCompose(state: BulkEmailState) {
  return renderRoutes([{ path: '/bulk-email/drafts/:id', element: <ComposePage /> }], {
    route: `/bulk-email/drafts/${state.email.id}`,
  });
}

/** A draft whose batch holds Ann Able alone. */
function draftState(overrides: Partial<BulkEmailState['email']> = {}): BulkEmailState {
  return { email: makeBulkEmail(overrides), batch: makeBatch([makeRow()]) };
}

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

  it('adds the filtered people to the batch and says how many joined', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    await userEvent.click(await screen.findByRole('button', { name: 'Add to batch' }));
    expect(await screen.findByText('Added 1 person; 1 was already in the batch.')).toBeVisible();
    expect(await screen.findByText('bea@example.org')).toBeVisible();
    expect(calls.adds).toEqual([{ filters: {} }]);
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
    const row = screen.getByText('Gil Gone').closest('tr');
    expect(row).toHaveTextContent('Account deactivated');
  });

  it('takes one person out once the trashcan is confirmed', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    await userEvent.click(
      await screen.findByRole('button', { name: 'Remove Ann Able from the batch' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(calls.removed).toEqual([1]));
  });

  it('clears the batch only from its confirmation', async () => {
    const calls = answerBulkEmail(draftState());
    renderCompose(draftState());
    await userEvent.click(await screen.findByRole('button', { name: 'Clear batch' }));
    expect(calls.clears).toBe(0);
    await userEvent.click(screen.getByRole('button', { name: 'Clear the batch' }));
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

  it('saves the subject by itself once the typing pauses', async () => {
    const calls = answerBulkEmail(draftState({ subject: '' }));
    renderCompose(draftState({ subject: '' }));
    await userEvent.type(await screen.findByRole('textbox', { name: /^Subject/ }), 'Fly-in');
    await waitFor(() => expect(calls.patches).toEqual([{ subject: 'Fly-in' }]), {
      timeout: 3000,
    });
    expect(await screen.findByText('Saved')).toBeVisible();
  });

  it('holds a sent email still and links to its results', async () => {
    const state = draftState({ status: 'sent', can_edit: false, sent_count: 1 });
    answerBulkEmail(state);
    renderCompose(state);
    const links = await screen.findAllByRole('link', { name: 'See who received it' });
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/bulk-email/sent/7',
      '/bulk-email/sent/7',
    ]);
    expect(screen.getByRole('textbox', { name: /^Subject/ })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Add to batch' })).toBeNull();
  });

  it('shows a scheduled email under a banner that can cancel the schedule', async () => {
    const state = draftState({
      status: 'queued',
      scheduled: true,
      start_at: '2026-04-07T15:00:00Z',
    });
    const calls = answerBulkEmail(state);
    renderCompose(state);
    const banner = await screen.findByRole('region', { name: 'Waiting to send' });
    expect(banner).toHaveTextContent('Scheduled for');
    await userEvent.click(within(banner).getByRole('button', { name: 'Cancel the schedule' }));
    await waitFor(() => expect(calls.actions).toEqual(['cancel']));
  });
});
