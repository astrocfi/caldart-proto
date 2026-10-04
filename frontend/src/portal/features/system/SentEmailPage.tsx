/**
 * `/portal/system/emails/:id`: one email of the log on a page of its own, answering
 * "what did we send this person?" — who it went to, what it was for, when, and what
 * became of it.
 *
 * The log keeps no copy of a message's text, which for a password reset or a
 * verification email would hold a working link.  A copy of a bulk email leads to that
 * email's page, where its message is.
 */
import type { JSX, ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { EmailLogEntry, EmailStatus } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
import { useEmailLogEntry } from './api';
import './sentEmail.css';

/** The page's way back, to the list with its filters as the browser left them. */
const BACK = <Link to="/system/emails">Back to sent emails</Link>;

/** Each status's dot and word: green sent, red failed or bounced. */
const STATUS: Record<EmailStatus, { tone: StatusTone; label: string }> = {
  sent: { tone: 'current', label: 'Sent' },
  failed: { tone: 'expired', label: 'Failed' },
  bounced: { tone: 'expired', label: 'Bounced' },
};

/** Renders one logged email, or why it cannot be shown. */
export function SentEmailPage(): JSX.Element {
  const id = Number(useParams().id);
  const entry = useEmailLogEntry(id);

  if (entry.isError) {
    const isMissing = entry.error instanceof ApiError && entry.error.status === 404;
    return (
      <Page title="Sent email" actions={BACK}>
        <EmptyState
          title={isMissing ? 'That email is not in the log' : "That email didn't load"}
          description={isMissing ? undefined : 'Try again in a moment.'}
        />
      </Page>
    );
  }

  if (entry.data === undefined) {
    return (
      <Page title="Sent email" actions={BACK}>
        <p className="muted" role="status">
          Loading the email…
        </p>
      </Page>
    );
  }

  return (
    <Page title="Sent email" tabTitle={entry.data.subject} actions={BACK}>
      <EmailCard entry={entry.data} />
    </Page>
  );
}

/** The email's facts, one line each, and where its message is. */
function EmailCard({ entry }: { entry: EmailLogEntry }): JSX.Element {
  const status = STATUS[entry.status];
  const facts: [string, ReactNode][] = [
    ['To', entry.user_name === '' ? entry.to_email : `${entry.user_name}, ${entry.to_email}`],
    ['For', entry.purpose_label],
    ['Sent', <DateText key="sent" value={entry.sent_at} withTime />],
    ['Status', <StatusDot key="status" tone={status.tone} label={status.label} />],
  ];
  if (entry.error !== '') facts.push(['Error', entry.error]);
  if (entry.bounced_at !== null) {
    facts.push(['Bounced on', <DateText key="bounced" value={entry.bounced_at} withTime />]);
  }
  if (entry.bounce_detail !== '') facts.push(['Bounce report', entry.bounce_detail]);
  if (entry.attachments !== '') facts.push(['Attachments', entry.attachments]);

  return (
    <Card title={entry.subject}>
      <dl className="sent-email__facts">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {entry.link === '' ? (
        <p className="muted">
          The log keeps who an email went to and what it was for. It keeps no copy of the text.
        </p>
      ) : (
        <p>
          <Link to={entry.link}>Open the bulk email</Link>
        </p>
      )}
    </Card>
  );
}
