/**
 * `/bulk-email/sent`: every bulk email that has started sending, the most
 * recently started first, one line each with its counts.
 *
 * The subject opens the send's own page. A send in progress has **Stop**, and a
 * stopped one **Send the rest**; both ask first. The list is read again every
 * few seconds while a send is in progress.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailSummary } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { recipientsCsvUrl, useBulkEmailAction, useSentEmails } from './api';
import './bulk-email.css';
import { actionError, RESUMED_MESSAGE, STOPPING_MESSAGE } from './SendStatus';
import { statusLabel, statusTone } from './status';

/** Every started send, with Stop and Send the rest where they apply. */
export function SentPage(): JSX.Element {
  const sent = useSentEmails();
  const stop = useBulkEmailAction('stop');
  const resume = useBulkEmailAction('resume');
  const toast = useToast();
  const rows = sent.data ?? [];

  const handleStop = (id: number): Promise<unknown> =>
    stop.mutateAsync(id).then(() => toast.show(STOPPING_MESSAGE, 'success'));
  const handleResume = (id: number): Promise<unknown> =>
    resume.mutateAsync(id).then(() => toast.show(RESUMED_MESSAGE, 'success'));

  const failure = stop.error ?? resume.error;

  return (
    <Page
      title="Sent"
      eyebrow="Bulk Email"
      lede="Every bulk email that has gone out, or is going out now, and what became of it."
    >
      <Card>
        {failure === null ? null : (
          <p className="field__error" role="alert">
            {actionError(failure)}
          </p>
        )}
        {sent.isError ? (
          <p className="field__error" role="alert">
            The sent bulk emails could not be loaded.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={sentColumns(handleStop, handleResume)}
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

/** The table's columns, wired to Stop and Send the rest. */
function sentColumns(
  handleStop: (id: number) => Promise<unknown>,
  handleResume: (id: number) => Promise<unknown>,
): Column<BulkEmailSummary>[] {
  return [
    {
      key: 'started_at',
      header: 'Date',
      width: '11rem',
      render: (row) => <DateText value={row.started_at} withTime />,
      sortValue: (row) => row.started_at,
    },
    {
      key: 'subject',
      header: 'Subject',
      render: (row) => <Link to={`/bulk-email/sent/${row.id}`}>{row.subject}</Link>,
      sortValue: (row) => row.subject,
    },
    { key: 'sender', header: 'From', render: (row) => row.sender || '—' },
    {
      key: 'status',
      header: 'Status',
      width: '8rem',
      render: (row) => (
        <span className="bulk-email__will-receive">
          <StatusDot tone={statusTone(row.status)} label={statusLabel(row)} />
          <span aria-hidden="true">{statusLabel(row)}</span>
        </span>
      ),
      sortValue: (row) => row.status,
    },
    {
      key: 'sent_count',
      header: 'Sent',
      numeric: true,
      width: '5rem',
      render: (row) => row.sent_count,
    },
    {
      key: 'failed_count',
      header: 'Failed',
      numeric: true,
      width: '5rem',
      render: (row) => row.failed_count,
    },
    {
      key: 'skipped_count',
      header: 'Skipped',
      numeric: true,
      width: '5rem',
      render: (row) => row.skipped_count,
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '14rem',
      render: (row) => (
        <span className="cluster">
          <RowAction row={row} onStop={handleStop} onResume={handleResume} />
          <a
            className="button button--quiet button--small"
            href={recipientsCsvUrl(row.id)}
            aria-label={`Download the results of ${row.subject}`}
            download
          >
            CSV
          </a>
        </span>
      ),
    },
  ];
}

interface RowActionProps {
  row: BulkEmailSummary;
  onStop: (id: number) => Promise<unknown>;
  onResume: (id: number) => Promise<unknown>;
}

/** **Stop** on a send in progress, **Send the rest** on a stopped one, else nothing. */
function RowAction({ row, onStop, onResume }: RowActionProps): JSX.Element | null {
  if (row.status === 'sending' && !row.stop_requested) {
    return (
      <ConfirmButton
        label="Stop"
        choices={[{ label: 'Stop now', variant: 'danger', onChoose: () => onStop(row.id) }]}
      >
        <p>Copies already sent cannot be called back. Nobody else is sent a copy.</p>
      </ConfirmButton>
    );
  }
  if (row.status === 'stopped') {
    return (
      <ConfirmButton
        label="Send the rest"
        choices={[{ label: 'Send them now', onChoose: () => onResume(row.id) }]}
      >
        <p>This sends the email to everybody a stop kept it from. Nobody gets it twice.</p>
      </ConfirmButton>
    );
  }
  return null;
}
