import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { CalloutDetail } from '@/portal/api/types';
import { formatDateAt } from '@/portal/components/DateText';
import { answerCallout, makeCallout } from '@test/fixtures/callouts';
import { renderRoutes } from '@test/render';
import {
  CalloutDetailPage,
  CLOSED_MESSAGE,
  REMINDING_MESSAGE,
  remindBlocked,
} from './CalloutDetailPage';

/** Render callout 7's page, answering as `callout`. */
function renderCallout(callout: CalloutDetail = makeCallout()) {
  const calls = answerCallout(callout);
  renderRoutes([{ path: '/bulk-email/callouts/:id', element: <CalloutDetailPage /> }], {
    route: '/bulk-email/callouts/7',
  });
  return calls;
}

/** The answers table, once it has loaded. */
async function answersTable(): Promise<HTMLElement> {
  return screen.findByRole('table', { name: 'Answers: 3 people' });
}

describe('CalloutDetailPage', () => {
  it('counts the answers by kind', async () => {
    renderCallout();

    expect(await screen.findByLabelText('Answers by kind')).toHaveTextContent(
      'Available0With limits1Not available0No answer2',
    );
  });

  // Each dot's words read once for a screen reader and once on screen.
  it("shows each person's answer, note, and what the member check reads", async () => {
    renderCallout();

    const ann = within(await answersTable())
      .getByText('Ann Able')
      .closest('tr');
    expect(ann).toHaveTextContent(
      `Ann AbleAvailable with limitsAvailable with limitsCleared to flyGOSaturday only` +
        `${formatDateAt('2026-04-06T18:00:00Z')}Marin DARTLVKN123AB`,
    );
  });

  it('puts the answer and the go/no-go next to the name, so a phone shows them', async () => {
    renderCallout();

    const headers = within(await answersTable())
      .getAllByRole('columnheader')
      // The sort arrow is drawn beside each heading; it is not part of its words.
      .map((header) => header.textContent?.replace(/[↕↑↓]/g, ''));
    expect(headers.slice(0, 3)).toEqual(['Name', 'Answer', 'Go/no-go']);
  });

  it('marks somebody the member check would not clear', async () => {
    renderCallout();

    const bea = within(await answersTable())
      .getByText('Bea Bell')
      .closest('tr');
    expect(bea).toHaveTextContent('NO-GO');
  });

  it('narrows the table to the people who have not answered', async () => {
    renderCallout();

    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Answer' }),
      'No answer yet',
    );

    const table = screen.getByRole('table', { name: 'Showing 2 of 3' });
    expect(within(table).queryByText('Ann Able')).not.toBeInTheDocument();
    expect(within(table).getByText('Cy Cole')).toBeInTheDocument();
  });

  it('reminds the people who have not answered, after asking', async () => {
    const calls = renderCallout();

    await userEvent.click(await screen.findByRole('button', { name: 'Remind non-responders' }));
    expect(screen.getByText(/sends the callout again to the 2 people/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Send reminders' }));

    await waitFor(() => expect(calls.reminds).toBe(1));
    expect(await screen.findByText(REMINDING_MESSAGE)).toBeInTheDocument();
  });

  it('lists each round of reminders', async () => {
    renderCallout(
      makeCallout({ reminders: [{ round: 1, requested_at: '2026-04-07T16:00:00Z', count: 2 }] }),
    );

    expect(await screen.findByRole('heading', { name: 'Reminders' })).toBeInTheDocument();
    expect(screen.getByText(/reminded 2 people\./)).toBeInTheDocument();
  });

  it('closes the callout, after asking', async () => {
    const calls = renderCallout();

    await userEvent.click(await screen.findByRole('button', { name: 'Close now' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close the callout' }));

    await waitFor(() => expect(calls.closes).toBe(1));
    expect(await screen.findByText(CLOSED_MESSAGE)).toBeInTheDocument();
  });

  it('offers no Close now once the callout has closed', async () => {
    renderCallout(makeCallout({ is_open: false, closed_at: '2026-04-07T16:00:00Z' }));

    await answersTable();
    expect(screen.queryByRole('button', { name: 'Close now' })).not.toBeInTheDocument();
  });

  it('keeps Remind non-responders off once everybody has answered, saying why', async () => {
    renderCallout(
      makeCallout({
        counts: { reached: 3, available: 3, limited: 0, unavailable: 0, no_answer: 0 },
      }),
    );

    expect(await screen.findByRole('button', { name: 'Remind non-responders' })).toBeDisabled();
    expect(screen.getByText('Everybody has answered.')).toBeInTheDocument();
  });

  it('says how many copies a close kept back', async () => {
    renderCallout(makeCallout({ is_open: false, closed_skipped: 2 }));

    expect(
      await screen.findByText('2 people were not sent the callout because its answers had closed.'),
    ).toBeInTheDocument();
  });

  it('downloads the answers', async () => {
    renderCallout();

    expect(await screen.findByRole('link', { name: 'Download answers' })).toHaveAttribute(
      'href',
      '/api/v1/bulk-email/callouts/7/answers.csv',
    );
  });
});

describe('remindBlocked', () => {
  it.each([
    [{ is_open: false }, 'This callout has closed, so nobody can answer it now.'],
    [
      { status: 'stopped' as const },
      'This callout was stopped. Send the rest first, then remind the others.',
    ],
    [{ status: 'sending' as const }, 'You can remind the others once sending finishes.'],
  ])('refuses %o', (overrides, reason) => {
    expect(remindBlocked(makeCallout(overrides))).toBe(reason);
  });

  it('lets a finished, open callout with people left be reminded', () => {
    expect(remindBlocked(makeCallout())).toBeNull();
  });

  it("offers Any answer as the answer filter's blank choice", async () => {
    renderCallout();

    const select = await screen.findByRole('combobox', { name: 'Answer' });
    expect(within(select).getAllByRole('option')[0]).toHaveTextContent('Any answer');
  });

  it('offers to reset the filters when nobody matches them', async () => {
    renderCallout();

    await userEvent.type(await screen.findByRole('searchbox', { name: 'Find a person' }), 'zzz');

    expect(await screen.findByText('Nobody matches these filters.')).toBeInTheDocument();
  });
});
