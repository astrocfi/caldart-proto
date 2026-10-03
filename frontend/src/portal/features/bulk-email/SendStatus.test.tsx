import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import { renderWithProviders } from '@test/render';
import type { BulkEmailDetail } from '@/portal/api/types';
import { SendStatus } from './SendStatus';

/** Render where `email` stands, answering its actions. */
function renderStatus(email: BulkEmailDetail) {
  const calls = answerBulkEmail({ email, batch: makeBatch([makeRow()]) });
  renderWithProviders(<SendStatus email={email} isDetailLinked />);
  return calls;
}

afterEach(() => {
  vi.useRealTimers();
});

describe('SendStatus', () => {
  it('counts down the undo window in minutes and seconds', () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-04-06T17:00:00Z'));
    renderStatus(makeBulkEmail({ status: 'queued', start_at: '2026-04-06T17:01:58Z' }));
    expect(screen.getByText('Sending in 1 min 58 s')).toBeVisible();
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByText('Sending in 1 min 56 s')).toBeVisible();
  });

  it('says nothing has gone yet once the countdown ends', () => {
    renderStatus(
      makeBulkEmail({ status: 'queued', start_at: new Date(Date.now() - 1000).toISOString() }),
    );
    expect(screen.getByText(/Nothing has been sent yet\. You can still cancel/)).toBeVisible();
  });

  it('cancels a queued send at once, with no second question', async () => {
    const calls = renderStatus(
      makeBulkEmail({ status: 'queued', start_at: new Date(Date.now() + 60_000).toISOString() }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(calls.actions).toEqual(['cancel']));
  });

  it('shows the progress of a send with Stop behind a confirmation', async () => {
    const calls = renderStatus(
      makeBulkEmail({
        status: 'sending',
        can_edit: false,
        sent_count: 12,
        remaining: 26,
        estimated_finish_at: new Date(Date.now() + 60_000).toISOString(),
      }),
    );
    expect(screen.getByText('Sending… 12 of 38 sent, about 1 minute left.')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Stop sending' }));
    await userEvent.click(screen.getByRole('button', { name: 'Stop now' }));
    await waitFor(() => expect(calls.actions).toEqual(['stop']));
  });

  it('offers Send the rest after a stop', async () => {
    const calls = renderStatus(
      makeBulkEmail({
        status: 'stopped',
        can_edit: false,
        batch_count: 3,
        sent_count: 1,
        stopped_by: 'Grace Holloway',
      }),
    );
    expect(screen.getByText(/^Stopped by Grace Holloway\./)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Send the rest' }));
    await userEvent.click(screen.getByRole('button', { name: 'Send them now' }));
    await waitFor(() => expect(calls.actions).toEqual(['resume']));
  });

  it('says everyone was sent a copy when nothing failed or was skipped', () => {
    renderStatus(makeBulkEmail({ status: 'sent', can_edit: false, sent_count: 51 }));
    expect(screen.getByText('Sent to 51 people. Everyone was sent a copy.')).toBeVisible();
  });
});
