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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { JSX, MouseEvent } from 'react';

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
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { StatusDot } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import type { FilterField, FilterValues } from '@/portal/reports/types';
import { DROP_ORDER } from './dropOrder';
import { isMoving, recipientsCsvUrl, useBatch } from './api';
import { CopyDialog } from './CopyDialog';
import './delivery.css';
import { useRetryFailed } from './deliveryApi';
import { actionError } from './SendStatus';
import { kindLabel, people, resultLabel, resultTone, wentCount } from './status';

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

/**
 * The results table's filters: the result, blank for any, and a search over names and
 * addresses.  They narrow the rows on screen; every copy's result arrives at once.
 */
const RESULT_FILTERS: readonly FilterField[] = [
  {
    key: 'result',
    label: 'Result',
    kind: 'select',
    placeholder: 'Any result',
    options: RESULT_CHOICES.map((choice) => ({ value: choice, label: resultLabel(choice) })),
  },
  { key: 'search', label: 'Find a person', kind: 'search', placeholder: 'Name or email' },
];

const NO_FILTERS: FilterValues = { result: '', search: '' };

/** The person whose copy is open, and the button that opened it. */
interface Viewing {
  row: BulkEmailBatchRow;
  trigger: HTMLButtonElement;
}

/** The delivery report of `email`, which has started sending. */
export function DeliveryReport({
  email,
  canRetry = true,
}: {
  email: BulkEmailDetail;
  /** False for a reader who may not act on the email: **Retry failed** is left out. */
  canRetry?: boolean;
}): JSX.Element {
  const batch = useBatch(email.id, isMoving(email.status));
  const [viewing, setViewing] = useState<Viewing | null>(null);

  const handleView = useCallback((row: BulkEmailBatchRow, trigger: HTMLButtonElement): void => {
    setViewing({ row, trigger });
  }, []);

  // Back to the View copy button that opened the copy, so a keyboard reader keeps their
  // place in the table: once the dialog has gone, since the page behind a modal dialog
  // takes no focus while it is open.
  const returnFocusRef = useRef<HTMLButtonElement | null>(null);
  const handleClose = (): void => {
    returnFocusRef.current = viewing?.trigger ?? null;
    setViewing(null);
  };
  useEffect(() => {
    if (viewing !== null) return;
    returnFocusRef.current?.focus();
    returnFocusRef.current = null;
  }, [viewing]);

  const columns = useMemo(() => resultColumns(handleView), [handleView]);

  return (
    <div className="stack">
      <DeliveryCounts email={email} />
      {canRetry ? <RetryFailed email={email} /> : null}
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
 * `Sent 37 · Failed 1 · Skipped 4 · Bounced 1 · Retried 1`, as a list of terms. Sent
 * counts every copy the mail server took, those that came back later included, so it
 * is the number the result line gives; Bounced says how many of them came back.
 */
export function DeliveryCounts({ email }: { email: BulkEmailDetail }): JSX.Element {
  const counts: [string, number][] = [
    ['Sent', wentCount(email)],
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
  const [filters, setFilters] = useState<FilterValues>(NO_FILTERS);
  const result = filters.result ?? '';
  const search = filters.search ?? '';
  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter(
      (row) =>
        (result === '' || row.status === result) &&
        (needle === '' ||
          row.name.toLowerCase().includes(needle) ||
          row.email.toLowerCase().includes(needle)),
    );
  }, [rows, search, result]);

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
  };
  const isFiltered = result !== '' || search.trim() !== '';

  return (
    <DataTable
      singleLine
      columns={columns}
      rows={shown}
      rowKey={(row) => row.id}
      caption={resultsCaption(shown.length, rows.length)}
      filters={
        <FilterBar
          fields={RESULT_FILTERS}
          values={filters}
          onChange={handleFilterChange}
          label="Filter the results"
        />
      }
      emptyTitle="Nobody to show"
      emptyDescription={isFiltered ? 'Nobody matches these filters.' : undefined}
      emptyAction={
        isFiltered ? (
          <Button
            variant="secondary"
            onClick={() => setFilters(clearedValues(RESULT_FILTERS, filters))}
          >
            Reset filters
          </Button>
        ) : undefined
      }
      isLoading={isLoading}
    />
  );
}

/**
 * A narrowable table's caption: `Results: 39 people`, or `Showing 2 of 39` once a menu
 * or a search narrows it.
 *
 * @param shown how many lines the table shows.
 * @param total how many there are in all.
 * @param label what the table holds, `Results` unless given.
 */
export function resultsCaption(shown: number, total: number, label = 'Results'): string {
  return shown === total ? `${label}: ${people(total)}` : `Showing ${shown} of ${total}`;
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
            <DateText value={retry.requested_at} withTime twelveHour />
            {`: ${retry.requested_by || 'A deleted account'} sent ${people(retry.count)} a fresh copy.`}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The results table's columns: the person's name, which tells the rows apart, what
 * became of their copy, the address, the reason, which wraps, and last **View copy**
 * for every copy that was tried, which stays in sight with the name and the result.
 * Their DART, their kind, when it was tried, then the address give way, in that order,
 * when the table would not fit its card; on a phone the result wraps and the name
 * narrows so the copy stays in sight.
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
      minWidth: '11rem',
      isIdentity: true,
      render: (row) => row.name,
      sortValue: (row) => row.name,
    },
    {
      key: 'status',
      header: 'Result',
      width: '9rem',
      keepInSight: true,
      narrowWidth: '6.5rem',
      render: (row) => (
        <span className="bulk-email__will-receive">
          <StatusDot tone={resultTone(row.status)} label={resultLabel(row.status)} />
          <span aria-hidden="true">{resultLabel(row.status)}</span>
        </span>
      ),
      sortValue: (row) => row.status,
    },
    {
      key: 'copy',
      header: 'Copy',
      isActions: true,
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
    {
      key: 'email',
      header: 'Email',
      minWidth: '13rem',
      dropOrder: DROP_ORDER.address,
      render: (row) => row.email,
      sortValue: (row) => row.email,
    },
    {
      key: 'reason',
      header: 'Reason',
      minWidth: '10rem',
      wrap: true,
      render: (row) => row.reason || '—',
    },
    {
      key: 'tried_at',
      header: 'Tried at',
      width: '11.5rem',
      dropOrder: DROP_ORDER.triedAt,
      render: (row) => <DateText value={row.tried_at} withTime twelveHour />,
      sortValue: (row) => row.tried_at,
    },
    {
      key: 'kind',
      header: 'Kind',
      width: '5.5rem',
      dropOrder: DROP_ORDER.kind,
      render: (row) => kindLabel(row.kind),
    },
    {
      key: 'dart',
      header: 'DART',
      width: '8rem',
      dropOrder: DROP_ORDER.dart,
      render: (row) => row.dart_name || '—',
    },
  ];
}
