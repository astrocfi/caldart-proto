/**
 * `/bulk-email/sent`: every bulk email that has started sending, the most
 * recently started first, one line each with its counts.
 *
 * The subject opens the send's own page. A send in progress offers **Stop…** and
 * a stopped one **Send the rest…**, each of which opens that page, where the
 * action asks first and the progress shows; every other line offers **Download
 * results**. The list is read again every few seconds while a send is in progress.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailSummary } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusChip';
import { recipientsCsvUrl, useSentEmails } from './api';
import './bulk-email.css';
import { DuplicateButton } from './DuplicateButton';
import { statusLabel, statusTone } from './status';

/** Every started send, one line each. */
export function SentPage(): JSX.Element {
  const sent = useSentEmails();
  const rows = sent.data ?? [];

  return (
    <Page
      title="Sent"
      eyebrow="Bulk Email"
      lede="Every bulk email that has gone out, or is going out now, and what became of it."
    >
      <Card>
        {sent.isError ? (
          <p className="field__error" role="alert">
            The sent bulk emails could not be loaded.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={SENT_COLUMNS}
            rows={rows}
            rowKey={(row) => row.id}
            caption={`${rows.length} bulk ${rows.length === 1 ? 'email' : 'emails'} sent`}
            emptyTitle="No bulk email has been sent"
            isLoading={sent.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}

/** The table's columns, the subject first. */
export const SENT_COLUMNS: Column<BulkEmailSummary>[] = [
  {
    key: 'subject',
    header: 'Subject',
    minWidth: '16rem',
    render: (row) => <Link to={`/bulk-email/sent/${row.id}`}>{row.subject}</Link>,
    sortValue: (row) => row.subject,
  },
  {
    key: 'started_at',
    header: 'Date',
    width: '6.5rem',
    render: (row) => <DateText value={row.started_at} />,
    sortValue: (row) => row.started_at,
  },
  {
    key: 'email_type_name',
    header: 'Type',
    width: '7rem',
    render: (row) => row.email_type_name || '—',
    sortValue: (row) => row.email_type_name,
  },
  { key: 'sender', header: 'From', width: '6.25rem', render: (row) => row.sender || '—' },
  {
    key: 'status',
    header: 'Status',
    width: '6.5rem',
    render: (row) => (
      <span className="bulk-email__will-receive">
        <StatusDot tone={statusTone(row.status)} label={statusLabel(row)} />
        <span aria-hidden="true">{statusLabel(row)}</span>
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
  { key: 'actions', header: 'Actions', width: '9rem', render: (row) => <RowAction row={row} /> },
  {
    key: 'duplicate',
    header: 'Reuse',
    width: '8rem',
    render: (row) => <DuplicateButton emailId={row.id} subject={row.subject} />,
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
