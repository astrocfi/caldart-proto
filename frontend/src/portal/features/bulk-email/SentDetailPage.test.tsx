import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { BulkEmailDetail } from '@/portal/api/types';
import { formatDateAt } from '@/portal/components/DateText';
import { EMAIL_FRAME_SANDBOX, withNewTabLinks } from '@/portal/components/EmailFrame';
import {
  LEADER_SENDER,
  answerBulkEmail,
  answerSender,
  makeBatch,
  makeBulkEmail,
  makeRow,
} from '@test/fixtures/bulkEmail';
import { makeUser, signedInAs } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { SentDetailPage } from './SentDetailPage';

/** Render the Sent page of a finished send to Ann, with Bea's copy refused. */
function renderSent(overrides: Partial<BulkEmailDetail> = {}) {
  answerBulkEmail({
    email: makeBulkEmail({
      ...overrides,
      status: 'sent',
      can_edit: false,
      batch_count: 2,
      sent_count: 1,
      failed_count: 1,
      started_at: '2026-04-06T17:00:00Z',
    }),
    batch: makeBatch([
      makeRow({ status: 'sent', tried_at: '2026-04-06T17:00:02Z' }),
      makeRow({
        id: 2,
        name: 'Bea Bell',
        email: 'bea@example.org',
        status: 'failed',
        will_receive: false,
        reason: 'Refused by the mail server',
      }),
    ]),
  });
  return renderRoutes([{ path: '/bulk-email/sent/:id', element: <SentDetailPage /> }], {
    route: '/bulk-email/sent/7',
  });
}

describe('SentDetailPage', () => {
  it("shows a co-leader another leader's email to read, without its actions", async () => {
    answerSender(LEADER_SENDER);
    server.use(signedInAs(makeUser({ id: 99, roles: ['member', 'dart_leader'] })));
    renderSent();
    expect(
      await screen.findByText('Grace Holloway sent this email to your DART. You can read it here.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Duplicate' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry failed' })).not.toBeInTheDocument();
  });

  it('offers Duplicate with its whole question under Where it stands', async () => {
    const user = userEvent.setup();
    renderSent();
    await user.click(await screen.findByRole('button', { name: 'Duplicate' }));
    expect(screen.getByRole('button', { name: 'Copy the message and the people' })).toBeVisible();
  });

  it('says what the send came to', async () => {
    renderSent();
    expect(
      await screen.findByText('Sent to 1 person. 1 failed and 0 were skipped.'),
    ).toHaveAttribute('role', 'status');
  });

  it('lists every person with their result and the reason', async () => {
    renderSent();
    const row = (await screen.findByText('bea@example.org')).closest('tr');
    expect(row).toHaveTextContent('Refused by the mail server');
  });

  it('shows the message as it was sent, in a sandboxed frame', async () => {
    renderSent();
    const frame = await screen.findByTitle('The message as it was sent');
    expect([frame.getAttribute('sandbox'), frame.getAttribute('srcdoc')]).toEqual([
      EMAIL_FRAME_SANDBOX,
      withNewTabLinks('<html><body><h1>Hangar day</h1><p>Bring gloves.</p></body></html>'),
    ]);
  });

  it('says the fields show as written when the message fills any in', async () => {
    renderSent({ body: '<p>Dear {first_name|friend},</p>' });
    expect(await screen.findByText(/Fields such as \{first_name\} show as written/)).toBeVisible();
  });

  it('says nothing of fields when the message fills none in', async () => {
    renderSent();
    await screen.findByTitle('The message as it was sent');
    expect(screen.queryByText(/Fields such as/)).toBeNull();
  });

  it('names the type it was sent as', async () => {
    renderSent();
    expect(await screen.findByText('Type: Operational')).toBeVisible();
  });

  it('offers the results as a download', async () => {
    renderSent();
    expect(await screen.findByRole('link', { name: 'Download results' })).toHaveAttribute(
      'href',
      '/api/v1/bulk-email/7/recipients.csv',
    );
  });

  it('says who sent it and when, on the 12-hour clock', async () => {
    renderSent();
    expect(
      await screen.findByText(
        `Sent by Grace Holloway on ${formatDateAt('2026-04-06T17:00:00Z')}.`,
      ),
    ).toBeVisible();
  });

  it('puts the name first in the results, with a real width', async () => {
    renderSent();
    const table = await screen.findByRole('table');
    const first = within(table).getAllByRole('columnheader')[0];
    expect([first?.textContent, table.style.minWidth.includes('11rem + 9rem')]).toEqual([
      'Name',
      true,
    ]);
  });

  it('puts the result and View copy next to the name, so a phone shows them', async () => {
    renderSent();
    const table = await screen.findByRole('table');
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((header) => header.textContent);
    expect(headers.slice(0, 3)).toEqual(['Name', 'Result', 'Copy']);
  });
});
