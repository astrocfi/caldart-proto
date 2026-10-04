import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, delay, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { answerBulkEmail, makeBatch, makeBulkEmail, makeRow } from '@test/fixtures/bulkEmail';
import type { BulkEmailState } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailDetail, BulkEmailFinding } from '@/portal/api/types';
import { CHECKS_WAIT_MS, missingSteps, SendCard, sendSoonerLabel } from './SendCard';
import type { Autosave, SaveState } from './useAutosave';
import { mismatchMessage } from './SendConfirm';

/** A warning the checks may find. */
const BROKEN_LINK: BulkEmailFinding = {
  code: 'link_broken',
  level: 'warning',
  message: 'This link does not load (the site answered 404): https://example.org/gone',
};

/** An error the checks may find. */
const BAD_REPLY_TO: BulkEmailFinding = {
  code: 'reply_to',
  level: 'error',
  message: 'Replies would go to ops, which is not a valid email address.',
};

/**
 * Render the card for `email`, with the subject and message it holds, saved, and
 * the checks finding `findings`.
 */
function renderCard(
  email: BulkEmailDetail,
  findings: BulkEmailFinding[] = [],
  saving: { saveState?: SaveState; saveErrors?: Autosave['errors'] } = {},
  handleFixField: (field: 'subject' | 'body') => void = () => undefined,
) {
  const state: BulkEmailState = { email, batch: makeBatch([makeRow()]), findings };
  const calls = answerBulkEmail(state);
  renderWithProviders(
    <SendCard
      email={email}
      subject={email.subject}
      body={email.body}
      onBeforeSend={() => Promise.resolve(true)}
      saveState={saving.saveState ?? 'saved'}
      saveErrors={saving.saveErrors ?? {}}
      onFixField={handleFixField}
    />,
  );
  return Object.assign(calls, { state });
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
    renderCard(makeBulkEmail({ body: '' }));
    expect(screen.getByText('Write the message.')).toBeVisible();
    expect(screen.queryByRole('button', { name: /^Send to/ })).toBeNull();
    // With no message there is no preview to ask for; the checks still answer.
    await screen.findByText('Nothing else to fix.');
  });

  it('confirms a small send without asking for the count, saying when it starts', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 3 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    const confirm = await screen.findByRole('region', { name: 'Confirm sending' });
    expect(confirm).toHaveTextContent(
      'This sends Hangar day to 3 people. Sending starts in 2 minutes, and until then you can cancel it.',
    );
    // Cancel has the focus, so Enter pressed twice does not send by accident.
    expect(within(confirm).getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Send now' }));
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: null, start_at: null }]));
  });

  it('keeps a large send off until the right count is typed, and says when it is wrong', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 52, confirm_above: 50 }));
    await userEvent.click(screen.getByRole('button', { name: 'Send to 52 people' }));
    const send = await screen.findByRole('button', { name: 'Send now' });
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
    await screen.findByRole('region', { name: 'Confirm sending' });
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
    await userEvent.type(await screen.findByRole('textbox', { name: 'Type 52 to confirm' }), '52');
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
    expect(await screen.findByRole('region', { name: 'Confirm sending' })).toHaveTextContent(
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

  it('sends a scheduled email sooner instead, after the undo window', async () => {
    const calls = renderCard(
      makeBulkEmail({ status: 'queued', scheduled: true, start_at: '2026-10-04T15:00:00Z' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send in 2 minutes instead' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Send now' }));
    await waitFor(() => expect(calls.sends).toEqual([{ confirm_count: null, start_at: null }]));
  });

  it('keeps Send off while the words typed are still saving', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 3 }), [], { saveState: 'saving' });
    expect(screen.getByRole('button', { name: 'Send to 3 people' })).toBeDisabled();
    await waitFor(() => expect(calls.previews).toHaveLength(1));
  });

  it('lists a refused save as a mistake to fix, and keeps Send off', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 3 }), [], {
      saveState: 'failed',
      saveErrors: { subject: '{nickname} is not one of the fields.' },
    });
    const checks = screen.getByRole('region', { name: 'Checks' });
    expect(within(checks).getByRole('list', { name: 'Not saved' })).toHaveTextContent(
      'Must fix: Your subject has a mistake: {nickname} is not one of the fields.',
    );
    expect(screen.getByRole('button', { name: 'Send to 3 people' })).toBeDisabled();
    await waitFor(() => expect(calls.previews).toHaveLength(1));
  });

  it('puts the focus in the field a refused save names, from its link', async () => {
    const handleFix = vi.fn();
    const calls = renderCard(
      makeBulkEmail({ receiving_count: 3 }),
      [],
      { saveState: 'failed', saveErrors: { subject: '{nickname} is not one of the fields.' } },
      handleFix,
    );
    await userEvent.click(screen.getByRole('link', { name: 'Fix it under 2. What it says.' }));
    expect(handleFix).toHaveBeenCalledWith('subject');
    await waitFor(() => expect(calls.previews).toHaveLength(1));
  });

  it('says nothing else needs fixing, without a green dot, while steps remain', async () => {
    renderCard(makeBulkEmail({ body: '' }));
    expect(await screen.findByText('Nothing else to fix.')).toBeVisible();
    expect(screen.queryByText('No problems found.')).toBeNull();
  });

  it('names the undo wait on the button that sends a scheduled email sooner', () => {
    expect([sendSoonerLabel(120), sendSoonerLabel(0)]).toEqual([
      'Send in 2 minutes instead',
      'Send now instead',
    ]);
  });

  it('runs the checks as it opens and lists what they find', async () => {
    renderCard(makeBulkEmail(), [BROKEN_LINK]);
    const checks = screen.getByRole('region', { name: 'Checks' });
    expect(await within(checks).findByText(BROKEN_LINK.message)).toBeVisible();
  });

  it('lets a warning through to the confirmation', async () => {
    renderCard(makeBulkEmail({ receiving_count: 3 }), [BROKEN_LINK]);
    await screen.findByText('You can still send.');
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    expect(await screen.findByRole('region', { name: 'Confirm sending' })).toBeVisible();
  });

  it('keeps Send off while the checks list an error', async () => {
    renderCard(makeBulkEmail({ receiving_count: 3 }), [BAD_REPLY_TO]);
    await screen.findByText(BAD_REPLY_TO.message);
    expect(screen.getByRole('button', { name: 'Send to 3 people' })).toBeDisabled();
  });

  it('runs the checks again before the confirmation, and stops on an error', async () => {
    const calls = renderCard(makeBulkEmail({ receiving_count: 3 }));
    await screen.findByText('No problems found.');
    const before = calls.checks;
    calls.state.findings = [BAD_REPLY_TO];
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    await screen.findByText(BAD_REPLY_TO.message);
    expect([
      calls.checks - before,
      screen.queryByRole('region', { name: 'Confirm sending' }),
    ]).toEqual([1, null]);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Check again' })).toHaveFocus());
  });

  it('lists the errors of a send the server refused under checks', async () => {
    renderCard(makeBulkEmail({ receiving_count: 3 }));
    server.use(
      http.post(`${API}/bulk-email/7/send`, () =>
        HttpResponse.json({ checks: [BAD_REPLY_TO] }, { status: 400 }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Send now' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(BAD_REPLY_TO.message);
  });

  it('opens the confirmation when the checks fail, and says they could not run', async () => {
    renderCard(makeBulkEmail({ receiving_count: 3 }));
    server.use(
      http.post(`${API}/bulk-email/7/checks`, () => HttpResponse.json({}, { status: 500 })),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Send to 3 people' }));
    expect(await screen.findByRole('region', { name: 'Confirm sending' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Checks' })).toHaveTextContent(
      'The checks could not run. You can still send.',
    );
  });

  it('opens the confirmation without waiting on slow checks for long', async () => {
    renderCard(makeBulkEmail({ receiving_count: 3 }));
    await screen.findByText('No problems found.');
    server.use(
      http.post(`${API}/bulk-email/7/checks`, async () => {
        await delay('infinite');
        return HttpResponse.json([]);
      }),
    );
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      await user.click(screen.getByRole('button', { name: 'Send to 3 people' }));
      await vi.advanceTimersByTimeAsync(CHECKS_WAIT_MS);
      expect(await screen.findByRole('region', { name: 'Confirm sending' })).toBeVisible();
    } finally {
      vi.useRealTimers();
    }
  });
});
