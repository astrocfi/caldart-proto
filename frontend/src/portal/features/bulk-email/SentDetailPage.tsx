/**
 * `/bulk-email/sent/:id`: one bulk email that has started sending.
 *
 * At the top are the subject, who sent it and when, and where it stands: the
 * progress with **Stop** while it sends, or the counts, with **Send the rest**
 * after a stop. Then the message as it was sent, and one line per person in the
 * batch with what became of their copy and why, which **Download results**
 * saves as a spreadsheet. The page is read again every few seconds while the
 * email is sending.
 */
import { useMemo, useState } from 'react';
import type { ChangeEvent, JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { BulkEmailBatchRow, BulkEmailDetail } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText, formatDateTime } from '@/portal/components/DateText';
import { Loading } from '@/portal/components/Loading';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusChip';
import { isMoving, recipientsCsvUrl, useBatch, useBulkEmail } from './api';
import './bulk-email.css';
import { SendStatus } from './SendStatus';
import { kindLabel, people, resultLabel, resultTone } from './status';

/** One send's page: the counts, the message, and every person's result. */
export function SentDetailPage(): JSX.Element {
  const id = Number(useParams().id);
  const email = useBulkEmail(id);
  const batch = useBatch(id, email.data !== undefined && isMoving(email.data.status));

  if (email.isError) {
    return (
      <Page title="Sent bulk email" eyebrow="Bulk Email">
        <p className="field__error" role="alert">
          This email could not be loaded. <Link to="/bulk-email/sent">See every sent email</Link>.
        </p>
      </Page>
    );
  }
  if (email.data === undefined) return <Loading />;
  const sent = email.data;

  return (
    <Page title={sent.subject || 'Sent bulk email'} eyebrow="Bulk Email" lede={sentLede(sent)}>
      <Card title="Where it stands">
        {sent.status === 'draft' || sent.status === 'queued' ? (
          <p>
            This email has not started sending.{' '}
            <Link to={`/bulk-email/drafts/${sent.id}`}>Open it</Link>.
          </p>
        ) : (
          <SendStatus email={sent} />
        )}
      </Card>

      <Card title="The message">
        <p>
          <strong>{sent.subject}</strong>
        </p>
        <div className="bulk-email__body">{sent.body}</div>
      </Card>

      <Card title="Who received it">
        {batch.isError ? (
          <p className="field__error" role="alert">
            The results could not be loaded.
          </p>
        ) : (
          <Results rows={batch.data?.rows ?? []} isLoading={batch.isLoading} />
        )}
        <div className="cluster">
          <a className="button button--quiet" href={recipientsCsvUrl(sent.id)} download>
            Download results
          </a>
        </div>
      </Card>
    </Page>
  );
}

/** `Sent by Grace Holloway on 04/06/2026 10:00 to a batch of 41 people.` */
function sentLede(email: BulkEmailDetail): string {
  const from = email.sender ? `Sent by ${email.sender}` : 'Sent';
  const when = email.started_at === null ? '' : ` on ${formatDateTime(email.started_at)}`;
  return `${from}${when} to a batch of ${people(email.batch_count)}.`;
}

/** A search box and one line per person with their result. */
function Results({ rows, isLoading }: { rows: BulkEmailBatchRow[]; isLoading: boolean }) {
  const [search, setSearch] = useState('');
  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (needle === '') return rows;
    return rows.filter(
      (row) => row.name.toLowerCase().includes(needle) || row.email.toLowerCase().includes(needle),
    );
  }, [rows, search]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setSearch(event.target.value);
  };

  return (
    <div className="stack-tight">
      <label className="cluster">
        Find a person
        <input type="search" value={search} onChange={handleSearchChange} />
      </label>
      <DataTable
        singleLine
        columns={RESULT_COLUMNS}
        rows={shown}
        rowKey={(row) => row.id}
        caption={`Results: ${people(rows.length)}`}
        emptyTitle="Nobody to show"
        isLoading={isLoading}
      />
    </div>
  );
}

/** The results table's columns. */
const RESULT_COLUMNS: Column<BulkEmailBatchRow>[] = [
  { key: 'name', header: 'Name', render: (row) => row.name, sortValue: (row) => row.name },
  { key: 'email', header: 'Email', render: (row) => row.email, sortValue: (row) => row.email },
  { key: 'kind', header: 'Kind', width: '6rem', render: (row) => kindLabel(row.kind) },
  { key: 'dart', header: 'DART', render: (row) => row.dart_name || '—' },
  {
    key: 'status',
    header: 'Result',
    width: '11rem',
    render: (row) => (
      <span className="bulk-email__will-receive">
        <StatusDot tone={resultTone(row.status)} label={resultLabel(row.status)} />
        <span aria-hidden="true">{resultLabel(row.status)}</span>
      </span>
    ),
    sortValue: (row) => row.status,
  },
  { key: 'reason', header: 'Reason', render: (row) => row.reason || '—' },
  {
    key: 'tried_at',
    header: 'Tried at',
    width: '11rem',
    render: (row) => <DateText value={row.tried_at} withTime />,
    sortValue: (row) => row.tried_at,
  },
];
