/**
 * The delivery report on a sent bulk email's page: what became of every copy.
 *
 * The counts (sent, failed, skipped, bounced, and retried) come first, with **Retry
 * failed**, which sends a fresh copy to everybody whose copy the mail server refused,
 * after asking. Then one line per person, narrowed by result or by a name or address,
 * with the reason and when the copy was tried, and **View copy**, which shows that
 * person's copy exactly as it went. **Download results** saves the table as a
 * spreadsheet file, and the retries are listed with their times.
 */
import { useCallback, useMemo, useState } from 'react';
import type { ChangeEvent, JSX, MouseEvent } from 'react';

import type {
  BulkEmailBatchRow,
  BulkEmailDetail,
  BulkEmailRecipientStatus,
} from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { StatusDot } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { isMoving, recipientsCsvUrl, useBatch } from './api';
import { CopyDialog } from './CopyDialog';
import './delivery.css';
import { useRetryFailed } from './deliveryApi';
import { actionError } from './SendStatus';
import { kindLabel, people, resultLabel, resultTone } from './status';

/** What the screen says once Retry failed has been pressed. */
export const RETRYING_MESSAGE = 'The failed copies will be sent again within a minute.';

/** The results a reader can narrow the table to, in the order the menu offers them. */
const RESULT_CHOICES: readonly BulkEmailRecipientStatus[] = [
  'sent',
  'failed',
  'bounced',
  'skipped',
  'stopped',
  'pending',
];

/** The menu's value for every result. */
const ALL_RESULTS = 'all';

/** The person whose copy is open, and the button that opened it. */
interface Viewing {
  row: BulkEmailBatchRow;
  trigger: HTMLButtonElement;
}

/** The delivery report of `email`, which has started sending. */
export function DeliveryReport({ email }: { email: BulkEmailDetail }): JSX.Element {
  const batch = useBatch(email.id, isMoving(email.status));
  const [viewing, setViewing] = useState<Viewing | null>(null);

  const handleView = useCallback((row: BulkEmailBatchRow, trigger: HTMLButtonElement): void => {
    setViewing({ row, trigger });
  }, []);

  // Back to the View copy button that opened the copy, so a keyboard reader keeps
  // their place in the table.
  const handleClose = (): void => {
    viewing?.trigger.focus();
    setViewing(null);
  };

  const columns = useMemo(() => resultColumns(handleView), [handleView]);

  return (
    <div className="stack">
      <DeliveryCounts email={email} />
      <RetryFailed email={email} />
      {batch.isError ? (
        <p className="field__error" role="alert">
          The results could not be loaded.
        </p>
      ) : (
        <Results rows={batch.data?.rows ?? []} columns={columns} isLoading={batch.isLoading} />
      )}
      {viewing === null ? null : (
        <CopyDialog
          emailId={email.id}
          rowId={viewing.row.id}
          name={viewing.row.name}
          onClose={handleClose}
        />
      )}
      <div className="cluster">
        <a className="button button--quiet" href={recipientsCsvUrl(email.id)} download>
          Download results
        </a>
      </div>
      <Retries email={email} />
    </div>
  );
}

/**
 * `Delivered 36 · Failed 1 · Skipped 4 · Bounced 1 · Retried 1`, as a list of terms.
 * Delivered counts the copies sent that have not come back, so Delivered and Bounced
 * together are the copies the result line calls sent.
 */
export function DeliveryCounts({ email }: { email: BulkEmailDetail }): JSX.Element {
  const counts: [string, number][] = [
    ['Delivered', email.sent_count],
    ['Failed', email.failed_count],
    ['Skipped', email.skipped_count],
    ['Bounced', email.bounced_count],
    ['Retried', email.retried_count],
  ];
  return (
    <dl className="bulk-email__counts" aria-label="Copies by result">
      {counts.map(([label, count]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{count}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * **Retry failed**, behind a confirmation; disabled, with the reason, when there is
 * nothing to retry yet.
 */
function RetryFailed({ email }: { email: BulkEmailDetail }): JSX.Element {
  const retry = useRetryFailed(email.id);
  const toast = useToast();
  const reason = retryBlocked(email);

  return (
    <div className="stack-tight">
      <div className="cluster">
        <ConfirmButton
          label="Retry failed"
          disabled={reason !== null}
          choices={[
            {
              label: 'Retry now',
              onChoose: () =>
                retry.mutateAsync().then(() => toast.show(RETRYING_MESSAGE, 'success')),
            },
          ]}
        >
          <p>
            This sends a fresh copy to the {people(email.failed_count)} whose copy the mail server
            refused. Nobody already sent a copy gets another, and nobody whose copy bounced or who
            was skipped is sent one. It starts within a minute.
          </p>
        </ConfirmButton>
      </div>
      {reason === null ? null : <p className="muted">{reason}</p>}
      {retry.isError ? (
        <p className="field__error" role="alert">
          {actionError(retry.error)}
        </p>
      ) : null}
    </div>
  );
}

/** Why Retry failed cannot be pressed for `email` now, or null when it can. */
export function retryBlocked(email: BulkEmailDetail): string | null {
  if (email.failed_count === 0) return 'No copy failed, so there is nothing to retry.';
  if (email.status === 'stopped') {
    return 'This email was stopped. Send the rest first, then retry the failed copies.';
  }
  if (email.status !== 'sent') return 'You can retry the failed copies once sending finishes.';
  return null;
}

interface ResultsProps {
  rows: BulkEmailBatchRow[];
  columns: Column<BulkEmailBatchRow>[];
  isLoading: boolean;
}

/** The result menu, a search box, and one line per person with their result. */
function Results({ rows, columns, isLoading }: ResultsProps): JSX.Element {
  const [search, setSearch] = useState('');
  const [result, setResult] = useState<string>(ALL_RESULTS);
  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter(
      (row) =>
        (result === ALL_RESULTS || row.status === result) &&
        (needle === '' ||
          row.name.toLowerCase().includes(needle) ||
          row.email.toLowerCase().includes(needle)),
    );
  }, [rows, search, result]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setSearch(event.target.value);
  };
  const handleResultChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    setResult(event.target.value);
  };

  return (
    <div className="stack-tight">
      <div className="cluster">
        <label className="cluster">
          Result
          <select value={result} onChange={handleResultChange}>
            <option value={ALL_RESULTS}>Every result</option>
            {RESULT_CHOICES.map((choice) => (
              <option key={choice} value={choice}>
                {resultLabel(choice)}
              </option>
            ))}
          </select>
        </label>
        <label className="cluster">
          Find a person
          <input type="search" value={search} onChange={handleSearchChange} />
        </label>
      </div>
      <DataTable
        singleLine
        columns={columns}
        rows={shown}
        rowKey={(row) => row.id}
        caption={`Results: ${people(rows.length)}`}
        emptyTitle="Nobody to show"
        isLoading={isLoading}
      />
    </div>
  );
}

/** The retries, each with when it was pressed, by whom, and how many copies it queued. */
function Retries({ email }: { email: BulkEmailDetail }): JSX.Element | null {
  if (email.retries.length === 0) return null;
  return (
    <section className="stack-tight" aria-labelledby="bulk-email-retries">
      <h3 id="bulk-email-retries">Retries</h3>
      <ul className="bulk-email__retries">
        {email.retries.map((retry) => (
          <li key={retry.id}>
            <DateText value={retry.requested_at} withTime />
            {`: ${retry.requested_by || 'A deleted account'} sent ${people(retry.count)} a fresh copy.`}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The results table's columns: the person's name first, then what became of their
 * copy, then what a narrow screen scrolls to, ending with **View copy** for every
 * copy that was tried.
 *
 * @param onView opens a person's copy, given the row and the button pressed.
 */
export function resultColumns(
  onView: (row: BulkEmailBatchRow, trigger: HTMLButtonElement) => void,
): Column<BulkEmailBatchRow>[] {
  return [
    {
      key: 'name',
      header: 'Name',
      minWidth: '16rem',
      render: (row) => row.name,
      sortValue: (row) => row.name,
    },
    {
      key: 'email',
      header: 'Email',
      minWidth: '14rem',
      render: (row) => row.email,
      sortValue: (row) => row.email,
    },
    {
      key: 'status',
      header: 'Result',
      width: '10rem',
      render: (row) => (
        <span className="bulk-email__will-receive">
          <StatusDot tone={resultTone(row.status)} label={resultLabel(row.status)} />
          <span aria-hidden="true">{resultLabel(row.status)}</span>
        </span>
      ),
      sortValue: (row) => row.status,
    },
    { key: 'reason', header: 'Reason', minWidth: '12rem', render: (row) => row.reason || '—' },
    {
      key: 'tried_at',
      header: 'Tried at',
      width: '9.5rem',
      render: (row) => <DateText value={row.tried_at} withTime />,
      sortValue: (row) => row.tried_at,
    },
    { key: 'kind', header: 'Kind', width: '5.5rem', render: (row) => kindLabel(row.kind) },
    { key: 'dart', header: 'DART', width: '8rem', render: (row) => row.dart_name || '—' },
    {
      key: 'copy',
      header: 'Copy',
      width: '7rem',
      render: (row) =>
        row.tried_at === null ? (
          '—'
        ) : (
          <Button
            small
            variant="quiet"
            aria-label={`View the copy sent to ${row.name}`}
            onClick={(event: MouseEvent<HTMLButtonElement>) => onView(row, event.currentTarget)}
          >
            View copy
          </Button>
        ),
    },
  ];
}
