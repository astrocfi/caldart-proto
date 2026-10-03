import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailDetail } from '@/portal/api/types';
import { missingSteps, SendCard } from './SendCard';
import { mismatchMessage } from './SendConfirm';

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

describe('missingSteps', () => {
  it('lists what is still needed before sending', () => {
    expect(missingSteps({ receiving_count: 0, email_type: null }, ' ', '')).toEqual([
      'Choose a type.',
      'Write a subject.',
      'Write the message.',
      'Add people to the batch.',
    ]);
  });
});

describe('SendCard', () => {
  // Each waits for the preview the card asks for as it opens, so that request is
  // answered before the test ends and cannot reach the next test's server.
  it('asks for a type before offering Send', async () => {
    const calls = renderCard(makeBulkEmail({ email_type: null, email_type_name: '' }));
    expect(screen.getByText('Choose a type.')).toBeVisible();
    expect(screen.queryByRole('button', { name: /^Send to/ })).toBeNull();
    await waitFor(() => expect(calls.previews).toHaveLength(1));
  });

  it('names what is missing instead of offering Send', async () => {
    const calls = renderCard(makeBulkEmail({ body: '' }));
    expect(screen.getByText('Write the message.')).toBeVisible();
    expect(screen.queryByRole('button', { name: /^Send to/ })).toBeNull();
    await waitFor(() => expect(calls.previews).toHaveLength(1));
  });

  it('confirms a small send without asking for the count, saying when it starts', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 3 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    const confirm = screen.getByRole('region', { name: 'Confirm sending' });
    expect(confirm).toHaveTextContent(
      'This sends Hangar day to 3 people. Sending starts in 2 minutes, and until then you can cancel it.',
    );
    expect(within(confirm).getByRole('button', { name: 'Send now' })).toHaveFocus();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Send now' }));
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: null, start_at: null }]));
  });

  it('keeps a large send off until the right count is typed, and says when it is wrong', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 52, confirm_above: 50 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 52 people' }));
    const send = screen.getByRole('button', { name: 'Send now' });
    const count = screen.getByRole('textbox', { name: 'Type 52 to confirm' });
    expect(count).toHaveFocus();
    await userEvent.type(count, '51');
    expect(send).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent(mismatchMessage(52));
    await userEvent.clear(count);
    await userEvent.type(count, '52');
    expect(send).toBeEnabled();
    await userEvent.click(send);
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: 52, start_at: null }]));
  });

  it('closes the confirmation on Escape and puts the focus back on Send', async () => {
    renderCard(makeBulkEmail({ receiving_count: 3 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('region', { name: 'Confirm sending' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Send to 3 people' })).toHaveFocus();
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

  it('schedules for a chosen date and time, in twelve-hour words', async () => {
    const calls = renderCard(makeBulkEmail());
    await userEvent.click(screen.getByRole('button', { name: 'Schedule for later' }));
    const date = screen.getByLabelText('Date');
    expect(date).toHaveFocus();
    await userEvent.clear(date);
    await userEvent.type(date, '2026-10-04');
    await userEvent.selectOptions(screen.getByLabelText('Time'), '1:30 PM');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('region', { name: 'Confirm sending' })).toHaveTextContent(
      'It goes out on 10/04/2026 at 1:30 PM Pacific time.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Schedule it' }));
    await waitFor(() =>
      expect(calls.sends).toEqual([{ confirm_count: null, start_at: '2026-10-04T13:30' }]),
    );
  });

  it('closes the schedule on Escape and puts the focus back on its button', async () => {
    renderCard(makeBulkEmail());
    await userEvent.click(screen.getByRole('button', { name: 'Schedule for later' }));
    await userEvent.keyboard('{Escape}');
    expect(screen.getByRole('button', { name: 'Schedule for later' })).toHaveFocus();
  });

  it('opens Change the time at the time already chosen', async () => {
    renderCard(
      makeBulkEmail({ status: 'queued', scheduled: true, start_at: '2026-10-04T15:00:00Z' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Change the time' }));
    expect(screen.getByLabelText('Date')).toHaveValue('2026-10-04');
    expect(screen.getByLabelText('Time')).toHaveValue('08:00');
  });

  it('sends a scheduled email now instead, with the undo window', async () => {
    const calls = renderCard(
      makeBulkEmail({ status: 'queued', scheduled: true, start_at: '2026-10-04T15:00:00Z' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send now instead' }));
    await userEvent.click(screen.getByRole('button', { name: 'Send now' }));
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: null, start_at: null }]));
  });
});
