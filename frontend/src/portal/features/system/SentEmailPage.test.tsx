import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import type { EmailLogEntry } from '@/portal/api/types';
import { formatDateTime } from '@/portal/components/DateText';
import { SentEmailPage } from './SentEmailPage';

const FAILED: EmailLogEntry = {
  id: 902,
  to_email: 'marta@example.org',
  user_id: 37,
  user_name: 'Marta Reyes',
  purpose: 'password_reset',
  purpose_label: 'Password reset',
  subject: 'CalDART: reset your password',
  sent_at: '2026-01-07T08:00:00-08:00',
  status: 'failed',
  error: 'SMTPRecipientsRefused',
  attachments: '',
  bounced_at: null,
  bounce_detail: '',
  link: '',
};

/** Open the page for email `id`, the server answering with `entry` or a 404. */
function renderEmail(entry: EmailLogEntry | null, id = 902): void {
  server.use(
    http.get(`${API}/system/emails/${id}`, () =>
      entry === null
        ? HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
        : HttpResponse.json(entry),
    ),
  );
  renderRoutes([{ path: '/system/emails/:id', element: <SentEmailPage /> }], {
    route: `/system/emails/${id}`,
  });
}

describe('SentEmailPage', () => {
  it('heads the page with the subject', async () => {
    renderEmail(FAILED);
    expect(
      await screen.findByRole('heading', { name: 'CalDART: reset your password' }),
    ).toBeInTheDocument();
  });

  it('says who it went to, what it was for, and when', async () => {
    renderEmail(FAILED);
    await screen.findByRole('heading', { name: 'CalDART: reset your password' });
    expect(screen.getByText('Marta Reyes, marta@example.org')).toBeInTheDocument();
    expect(screen.getByText('Password reset')).toBeInTheDocument();
    expect(screen.getByText(formatDateTime(FAILED.sent_at))).toBeInTheDocument();
  });

  it('says what became of it, with the reason a send failed', async () => {
    renderEmail(FAILED);
    expect(await screen.findByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('SMTPRecipientsRefused')).toBeInTheDocument();
  });

  it('says when and why an email bounced', async () => {
    renderEmail({
      ...FAILED,
      status: 'bounced',
      error: '',
      bounced_at: '2026-01-08T12:00:00Z',
      bounce_detail: '5.1.1 550 User unknown',
    });
    expect(await screen.findByText('Bounced')).toBeInTheDocument();
    expect(screen.getByText('5.1.1 550 User unknown')).toBeInTheDocument();
  });

  it('leads to the bulk email a copy belongs to, where its message is', async () => {
    renderEmail({ ...FAILED, purpose_label: 'Bulk email', link: '/bulk-email/sent/9' });
    expect(await screen.findByRole('link', { name: 'Open the bulk email' })).toHaveAttribute(
      'href',
      '/bulk-email/sent/9',
    );
  });

  it('says the log keeps no copy of a message that belongs to no record', async () => {
    renderEmail(FAILED);
    expect(
      await screen.findByText(
        'The log keeps who an email went to and what it was for. It keeps no copy of the text.',
      ),
    ).toBeInTheDocument();
  });

  it('leads back to the list', async () => {
    renderEmail(FAILED);
    expect(await screen.findByRole('link', { name: 'Back to sent emails' })).toHaveAttribute(
      'href',
      '/system/emails',
    );
  });

  it('says so in plain words when the email is not in the log', async () => {
    renderEmail(null, 999);
    expect(await screen.findByText('That email is not in the log')).toBeInTheDocument();
  });
});
