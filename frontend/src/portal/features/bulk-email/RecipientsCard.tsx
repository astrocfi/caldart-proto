/**
 * Card 1 of the compose screen, **Who gets it**: the member list's filters, one
 * **Add to batch** button, and the batch itself.
 *
 * Each add puts everybody the filters choose into the batch, unless they are in
 * it already, and says how many joined. The table lists everybody in the batch,
 * which add brought them in, and whether they will receive the email or why not.
 * One person can be taken out with the trashcan, or everybody with **Clear
 * batch**; both ask first. **Download list** saves the batch as a spreadsheet.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { useDarts } from '@/portal/api/queries';
import type { BulkEmailAddResult, BulkEmailBatch, BulkEmailBatchRow } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { FilterBar } from '@/portal/components/FilterBar';
import { StatusDot } from '@/portal/components/StatusChip';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterValues } from '@/portal/reports/types';
import { batchCsvUrl, useAddToBatch, useBatch, useClearBatch, useRemoveFromBatch } from './api';
import { addSentence, batchSentence, kindLabel, people } from './status';

/** The member list's filters, less any only a subscription offers. */
const FILTER_FIELDS = listFilters(REPORTS.members);

/**
 * How long Add to batch waits before it reads the filters: longer than the filter
 * bar's pause, so words typed just before the press have been applied.
 */
const ADD_SETTLE_MS = SEARCH_DEBOUNCE_MS + 100;

/** What the card says when a request fails without a message of its own. */
const FALLBACK_ERROR = 'That did not work. Try again.';

interface RecipientsCardProps {
  emailId: number;
  /** False once the email has started sending: the batch is then shown, not changed. */
  isEditable: boolean;
}

/** The batch: build it with the filters, read it, and change it. */
export function RecipientsCard({ emailId, isEditable }: RecipientsCardProps): JSX.Element {
  const [filters, setFilters] = useState<FilterValues>({});
  const [lastAdd, setLastAdd] = useState<BulkEmailAddResult | null>(null);
  const [search, setSearch] = useState('');
  const [isSettling, setIsSettling] = useState(false);

  const darts = useDarts();
  const dartOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
    }),
    [darts.data],
  );

  const batch = useBatch(emailId);
  const add = useAddToBatch(emailId);
  const remove = useRemoveFromBatch(emailId);
  const clear = useClearBatch(emailId);

  // The filters as last applied, read by an add once the bar has settled.
  const filtersRef = useRef(filters);
  const addTimer = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (addTimer.current !== null) window.clearTimeout(addTimer.current);
    },
    [],
  );

  const handleFilterChange = (next: FilterValues): void => {
    filtersRef.current = next;
    setFilters(next);
  };

  const handleRemove = isEditable
    ? (rowId: number): Promise<unknown> => remove.mutateAsync(rowId)
    : undefined;

  // A search typed just before the press applies after a short pause, so the add
  // waits out that pause; otherwise it would add whoever the old filters chose.
  const handleAdd = (): void => {
    setLastAdd(null);
    setIsSettling(true);
    addTimer.current = window.setTimeout(() => {
      addTimer.current = null;
      setIsSettling(false);
      add.mutate(filtersRef.current, { onSuccess: (result) => setLastAdd(result) });
    }, ADD_SETTLE_MS);
  };

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setSearch(event.target.value);
  };

  const failure = add.error ?? remove.error ?? clear.error;

  return (
    <Card title="1. Who gets it" className="bulk-email__card">
      <p className="muted">
        Choose people with the filters, then press <strong>Add to batch</strong>. Add as many groups
        as you like: nobody is added twice.
      </p>
      {isEditable ? (
        <div className="stack">
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={handleFilterChange}
            options={dartOptions}
            label="Choose people to add"
          />
          <div className="cluster">
            <Button onClick={handleAdd} disabled={add.isPending || isSettling}>
              {add.isPending || isSettling ? 'Adding…' : 'Add to batch'}
            </Button>
          </div>
          {lastAdd === null ? null : <p role="status">{addSentence(lastAdd)}</p>}
        </div>
      ) : null}

      {failure === null ? null : (
        <p className="field__error" role="alert">
          {addComplaint(failure)}
        </p>
      )}

      {batch.isError ? (
        <p className="field__error" role="alert">
          The batch could not be loaded.
        </p>
      ) : (
        <BatchTable
          batch={batch.data}
          isLoading={batch.isLoading}
          search={search}
          onSearchChange={handleSearchChange}
          onRemove={handleRemove}
        />
      )}

      {batch.data !== undefined && batch.data.count > 0 ? (
        <div className="cluster">
          <a className="button button--quiet" href={batchCsvUrl(emailId)} download>
            Download list
          </a>
          {isEditable ? (
            <ConfirmButton
              label="Clear batch"
              choices={[
                {
                  label: 'Clear the batch',
                  variant: 'danger',
                  onChoose: () => clear.mutateAsync(),
                },
              ]}
            >
              <p>
                This takes all {people(batch.data.count)} out of the batch. The message is kept.
              </p>
            </ConfirmButton>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

interface BatchTableProps {
  batch: BulkEmailBatch | undefined;
  isLoading: boolean;
  search: string;
  onSearchChange: (event: ChangeEvent<HTMLInputElement>) => void;
  /** Takes one person out; left out when the batch can no longer change. */
  onRemove?: (rowId: number) => Promise<unknown>;
}

/** The count sentence, a search box, and one line per person in the batch. */
function BatchTable({
  batch,
  isLoading,
  search,
  onSearchChange: handleSearchChange,
  onRemove,
}: BatchTableProps): JSX.Element {
  const labels = useMemo(
    () => new Map((batch?.adds ?? []).map((add) => [add.id, add.label])),
    [batch?.adds],
  );
  const rows = useMemo(() => matching(batch?.rows ?? [], search), [batch?.rows, search]);

  return (
    <div className="stack-tight">
      {batch === undefined ? null : (
        <p>
          <strong>{batchSentence(batch.receiving, batch.skipped)}</strong>
        </p>
      )}
      {batch !== undefined && batch.count > 0 ? (
        <label className="cluster">
          Find in the batch
          <input type="search" value={search} onChange={handleSearchChange} />
        </label>
      ) : null}
      <DataTable
        singleLine
        columns={batchColumns(labels, onRemove)}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`The batch: ${people(batch?.count ?? 0)}`}
        emptyTitle="Nobody is in the batch yet"
        emptyDescription="Choose people with the filters above, then press Add to batch."
        isLoading={isLoading}
        initialSort={{ key: 'name', direction: 'asc' }}
      />
    </div>
  );
}

/** The rows whose name or address holds `search`, ignoring case. */
function matching(rows: BulkEmailBatchRow[], search: string): BulkEmailBatchRow[] {
  const needle = search.trim().toLowerCase();
  if (needle === '') return rows;
  return rows.filter(
    (row) => row.name.toLowerCase().includes(needle) || row.email.toLowerCase().includes(needle),
  );
}

/** The batch table's columns; the trashcan column only while the batch can change. */
function batchColumns(
  labels: Map<number, string>,
  onRemove: ((rowId: number) => Promise<unknown>) | undefined,
): Column<BulkEmailBatchRow>[] {
  const columns: Column<BulkEmailBatchRow>[] = [
    { key: 'name', header: 'Name', render: (row) => row.name, sortValue: (row) => row.name },
    { key: 'email', header: 'Email', render: (row) => row.email, sortValue: (row) => row.email },
    {
      key: 'kind',
      header: 'Kind',
      width: '6rem',
      render: (row) => kindLabel(row.kind),
      sortValue: (row) => row.kind,
    },
    {
      key: 'dart',
      header: 'DART',
      render: (row) => row.dart_name || '—',
      sortValue: (row) => row.dart_name,
    },
    {
      key: 'added_by',
      header: 'Added by',
      render: (row) => (row.added_by === null ? '—' : (labels.get(row.added_by) ?? '—')),
    },
    {
      key: 'will_receive',
      header: 'Will receive?',
      render: (row) => <WillReceive row={row} />,
      sortValue: (row) => (row.will_receive ? '' : row.reason),
    },
  ];
  if (onRemove === undefined) return columns;
  return [
    ...columns,
    {
      key: 'remove',
      header: 'Remove',
      width: '5rem',
      render: (row) => (
        <DeleteButton
          label={`Remove ${row.name || row.email} from the batch`}
          confirmLabel="Remove"
          onDelete={() => onRemove(row.id)}
        />
      ),
    },
  ];
}

/** A dot and *Yes*, or a dot and the reason the person is skipped. */
function WillReceive({ row }: { row: BulkEmailBatchRow }): JSX.Element {
  const words = row.will_receive ? 'Yes' : row.reason;
  return (
    <span className="bulk-email__will-receive">
      <StatusDot tone={row.will_receive ? 'current' : 'none'} label={words} />
      <span aria-hidden="true">{words}</span>
    </span>
  );
}

/**
 * The sentence a failed add, removal, or clear shows: a refused filter by its
 * label, such as *Expiring within (days): Enter a number.*, or the server's own.
 */
function addComplaint(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_ERROR;
  const body: unknown = error.body;
  if (body !== null && typeof body === 'object' && 'filters' in body) {
    const filters: unknown = body.filters;
    if (filters !== null && typeof filters === 'object' && !Array.isArray(filters)) {
      for (const [key, messages] of Object.entries(filters as Record<string, unknown>)) {
        if (!Array.isArray(messages) || typeof messages[0] !== 'string') continue;
        const label = FILTER_FIELDS.find((field) => field.key === key)?.label ?? key;
        return `${label}: ${messages[0]}`;
      }
    }
  }
  return error.message;
}
