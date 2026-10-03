import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailDetail } from '@/portal/api/types';
import { missingSteps, SendCard } from './SendCard';

/** Render the card for `email`, with the subject and message it holds, saved. */
function renderCard(email: BulkEmailDetail) {
  const state: BulkEmailState = { email, batch: makeBatch([makeRow()]) };
  const calls = answerBulkEmail(state);
  renderWithProviders(
    <SendCard
      email={email}
      subject={email.subject}
      body={email.body}
      onBeforeSend={() => Promise.resolve(true)}
    />,
  );
  return calls;
}

afterEach(() => {
  vi.useRealTimers();
});

describe('missingSteps', () => {
  it('lists what is still needed before sending', () => {
    expect(missingSteps({ receiving_count: 0 }, ' ', '')).toEqual([
      'Write a subject.',
      'Write the message.',
      'Add people to the batch.',
    ]);
  });
});

describe('SendCard', () => {
  it('names what is missing instead of offering Send', () => {
    renderCard(makeBulkEmail({ body: '' }));
    expect(screen.getByText('Write the message.')).toBeVisible();
    expect(screen.queryByRole('button', { name: /^Send to/ })).toBeNull();
  });

  it('confirms a small send without asking for the count', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 3 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    const confirm = screen.getByRole('region', { name: 'Confirm sending' });
    expect(confirm).toHaveTextContent('This sends Hangar day to 3 people.');
    await userEvent.click(within(confirm).getByRole('button', { name: 'Send now' }));
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: null, start_at: null }]));
  });

  it('keeps a large send off until the right count is typed', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 52, confirm_above: 50 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 52 people' }));
    const send = screen.getByRole('button', { name: 'Send now' });
    expect(send).toBeDisabled();
    const count = screen.getByRole('textbox', { name: 'Type 52 to confirm' });
    await userEvent.type(count, '51');
    expect(send).toBeDisabled();
    await userEvent.clear(count);
    await userEvent.type(count, '52');
    expect(send).toBeEnabled();
    await userEvent.click(send);
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: 52, start_at: null }]));
  });

  it('shows the server refusing a batch that changed meanwhile', async () => {
    renderCard(makeBulkEmail({ receiving_count: 52, confirm_above: 50 }));
    server.use(
      http.post(`${API}/bulk-email/7/send`, () =>
        HttpResponse.json(
          {
            confirm_count: ['The batch has changed: it now holds 53 people. Type the new count.'],
          },
          { status: 400 },
        ),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send to 52 people' }));
    await userEvent.type(screen.getByRole('textbox', { name: 'Type 52 to confirm' }), '52');
    await userEvent.click(screen.getByRole('button', { name: 'Send now' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('it now holds 53 people');
  });

  it('schedules for a chosen date and time after confirming it', async () => {
    const calls = renderCard(makeBulkEmail());
    await userEvent.click(screen.getByRole('button', { name: 'Schedule for later' }));
    const date = screen.getByLabelText('Date');
    await userEvent.clear(date);
    await userEvent.type(date, '2026-04-08');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('region', { name: 'Confirm sending' })).toHaveTextContent(
      'It goes out on 04/08/2026 at 08:00 Pacific time.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Schedule it' }));
    await waitFor(() =>
      expect(calls.sends).toEqual([{ confirm_count: null, start_at: '2026-04-08T08:00' }]),
    );
  });

  it('counts down the undo window with Cancel at hand', () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-04-06T17:00:00Z'));
    renderCard(makeBulkEmail({ status: 'queued', start_at: '2026-04-06T17:01:58Z' }));
    expect(screen.getByText('Sending in 1:58')).toBeVisible();
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(screen.getByText('Sending in 1:56')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled();
  });

  it('cancels a queued send at once, with no second question', async () => {
    const calls = renderCard(
      makeBulkEmail({ status: 'queued', start_at: new Date(Date.now() + 60_000).toISOString() }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(calls.actions).toEqual(['cancel']));
  });

  it('shows the progress of a send with Stop behind a confirmation', async () => {
    const calls = renderCard(
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
    const calls = renderCard(
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
});
