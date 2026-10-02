/**
 * The history card of the Bulk Email screen: every bulk email sent, the most
 * recent first, one line each, with its counts and its results as a CSV.
 * **Results** opens a send's per-person results under the table.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { BulkEmail } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { recipientsCsvUrl, useBulkEmail, useBulkEmails } from './api';
import { BulkEmailResults } from './BulkEmailResults';

function historyColumns(onOpen: (id: number) => void): Column<BulkEmail>[] {
  return [
    {
      key: 'created_at',
      header: 'Date',
      width: '12rem',
      render: (row) =>
        row.sent_at === null ? (
          <span title="This send stopped before every copy was tried; open its results.">
            <DateText value={row.created_at} /> <strong>Interrupted</strong>
          </span>
        ) : (
          <DateText value={row.created_at} />
        ),
      sortValue: (row) => row.created_at,
    },
    { key: 'subject', header: 'Subject', render: (row) => row.subject },
    { key: 'sender', header: 'From', render: (row) => row.sender || '—' },
    {
      key: 'sent_count',
      header: 'Sent',
      numeric: true,
      render: (row) => row.sent_count,
    },
    {
      key: 'failed_count',
      header: 'Failed',
      numeric: true,
      render: (row) => row.failed_count,
    },
    {
      key: 'skipped_count',
      header: 'Skipped',
      numeric: true,
      render: (row) => row.skipped_count,
    },
    {
      key: 'actions',
      header: 'Results',
      render: (row) => (
        <span className="cluster">
          <Button
            variant="quiet"
            small
            aria-label={`Results of ${row.subject}`}
            onClick={() => onOpen(row.id)}
          >
            Results
          </Button>
          <a
            className="button button--quiet button--small"
            href={recipientsCsvUrl(row.id)}
            aria-label={`Download the list of ${row.subject}`}
            download
          >
            CSV
          </a>
        </span>
      ),
    },
  ];
}

/** Every past send, and the results of the one opened. */
export function BulkEmailHistory(): JSX.Element {
  const [openId, setOpenId] = useState<number | null>(null);
  const history = useBulkEmails();
  const opened = useBulkEmail(openId);
  const rows = history.data ?? [];

  return (
    <Card eyebrow="History" title="Sent bulk emails">
      {history.isError ? (
        <p className="field__error" role="alert">
          The sent bulk emails could not be loaded.
        </p>
      ) : (
        <DataTable
          singleLine
          columns={historyColumns(setOpenId)}
          rows={rows}
          rowKey={(row) => row.id}
          caption={`${rows.length} bulk email${rows.length === 1 ? '' : 's'} sent`}
          emptyTitle="No bulk email has been sent"
          isLoading={history.isLoading}
        />
      )}
      {opened.data ? <BulkEmailResults sent={opened.data} /> : null}
      {opened.isError ? (
        <p className="field__error" role="alert">
          Those results could not be loaded.
        </p>
      ) : null}
    </Card>
  );
}
