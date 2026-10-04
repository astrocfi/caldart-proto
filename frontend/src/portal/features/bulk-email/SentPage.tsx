/**
 * `/bulk-email/sent`: every bulk email that has started sending, the most
 * recently started first, one line each with its counts.
 *
 * The subject opens the send's own page. A send in progress offers **Stop…** and
 * a stopped one **Send the rest…**, each of which opens that page, where the
 * action asks first and the progress shows; every other line offers **Download
 * results**. **Duplicate…** on every line opens that page too, where Duplicate asks
 * how to copy the email. The list is read again every few seconds while a send is in
 * progress.
 * CalDART management, who sees every sender's sends, also sees who sent each and the
 * DART a DART leader's send went to. A DART leader's screen speaks of their own emails.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailSummary } from '@/portal/api/types';
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { DROP_ORDER } from './dropOrder';
import { SenderNotice } from './SenderNotice';
import { recipientsCsvUrl, useBulkSender, useSentEmails } from './api';
import './bulk-email.css';
import { withSenderColumns } from './senderColumns';
import { statusLabel, statusTone } from './status';

/** Every started send, one line each. */
export function SentPage(): JSX.Element {
  const sent = useSentEmails();
  const sender = useBulkSender();
  const rows = sent.data ?? [];
  // A DART leader sees only their own emails, so the screen speaks of theirs.
  const isLeader = sender.data?.is_management === false;
  const canSend = sender.data?.can_send === true;

  return (
    <Page
      title="Sent"
      lede={
        isLeader
          ? 'The emails you have sent, or are sending now, and what became of each.'
          : 'Every bulk email that has gone out, or is going out now, and what became of it.'
      }
    >
      {sender.data === undefined ? null : <SenderNotice sender={sender.data} />}
      <Card>
        {sent.isError ? (
          <p className="field__error" role="alert">
            The sent bulk emails didn&apos;t load. Try again in a moment.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={withSenderColumns(SENT_COLUMNS, sender.data?.is_management === true)}
            rows={rows}
            rowKey={(row) => row.id}
            initialSort={{ key: 'started_at', direction: 'desc' }}
            caption={`${rows.length} bulk ${rows.length === 1 ? 'email' : 'emails'} sent`}
            emptyTitle={isLeader ? 'You have not sent an email yet' : 'No bulk email has been sent'}
            emptyDescription={
              isLeader
                ? 'Emails you send appear here once they start going out.'
                : 'Each bulk email appears here once it starts going out.'
            }
            emptyAction={
              canSend ? <ButtonLink to="/bulk-email/compose">New email</ButtonLink> : undefined
            }
            isLoading={sent.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}

/**
 * The table's columns: the subject, which tells the rows apart, then the date, the
 * status, the counts, and last the actions (the row's action and **Duplicate…**, one
 * above the other on a phone), which stay in sight. The type, then the DART, then who
 * sent it give way when the table would not fit its card.
 */
export const SENT_COLUMNS: Column<BulkEmailSummary>[] = [
  {
    key: 'subject',
    header: 'Subject',
    minWidth: '9rem',
    isIdentity: true,
    render: (row) => <Link to={`/bulk-email/sent/${row.id}`}>{row.subject}</Link>,
    sortValue: (row) => row.subject,
  },
  {
    key: 'actions',
    header: 'Actions',
    width: '15.25rem',
    isActions: true,
    narrowWidth: '9.5rem',
    render: (row) => (
      <span className="cluster cluster--nowrap">
        <RowAction row={row} />
        <Link
          className="button button--quiet button--small"
          to={`/bulk-email/sent/${row.id}`}
          aria-label={`Duplicate ${row.subject}`}
        >
          Duplicate…
        </Link>
      </span>
    ),
  },
  {
    key: 'started_at',
    header: 'Date',
    width: '6.5rem',
    noWrap: true,
    render: (row) => <DateText value={row.started_at} />,
    sortValue: (row) => row.started_at,
  },
  {
    key: 'email_type_name',
    header: 'Type',
    width: '7rem',
    dropOrder: DROP_ORDER.type,
    render: (row) => row.email_type_name || '—',
    sortValue: (row) => row.email_type_name,
  },
  {
    key: 'status',
    header: 'Status',
    width: '6rem',
    render: (row) => (
      <span className="bulk-email__will-receive">
        <StatusDot tone={statusTone(row.status)} label={statusLabel(row)} />
      </span>
    ),
    sortValue: (row) => row.status,
  },
  { key: 'sent_count', header: 'Sent', numeric: true, width: '4rem', render: (r) => r.sent_count },
  {
    key: 'failed_count',
    header: 'Failed',
    numeric: true,
    width: '4rem',
    render: (row) => row.failed_count,
  },
  {
    key: 'skipped_count',
    header: 'Skipped',
    numeric: true,
    width: '4.5rem',
    render: (row) => row.skipped_count,
  },
];

/**
 * **Stop…** on a send in progress and **Send the rest…** on a stopped one, each
 * opening the send's page; **Download results** on any other.
 */
function RowAction({ row }: { row: BulkEmailSummary }): JSX.Element {
  const isResumed = row.status === 'queued' && row.started_at !== null;
  if ((row.status === 'sending' && !row.stop_requested) || isResumed) {
    return (
      <Link
        className="button button--secondary button--small"
        to={`/bulk-email/sent/${row.id}`}
        aria-label={`Stop sending ${row.subject}`}
      >
        Stop…
      </Link>
    );
  }
  if (row.status === 'stopped') {
    return (
      <Link
        className="button button--secondary button--small"
        to={`/bulk-email/sent/${row.id}`}
        aria-label={`Send the rest of ${row.subject}`}
      >
        Send the rest…
      </Link>
    );
  }
  return (
    <a
      className="button button--quiet button--small"
      href={recipientsCsvUrl(row.id)}
      aria-label={`Download the results of ${row.subject}`}
      download
    >
      Download results
    </a>
  );
}
