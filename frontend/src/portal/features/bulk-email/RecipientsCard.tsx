/**
 * Card 1 of the compose screen, **Who gets it**: the member list's filters, one
 * **Add to batch** button, and the batch, the list of people the email goes to.
 *
 * Each add puts everybody the filters choose into the batch, unless they are in
 * it already, and says how many joined. The table lists everybody in the batch in
 * surname order, which filters chose them, and whether they will receive the email
 * or why not; it shows the first ten until **Show all** is pressed. One person can be
 * taken out with the trashcan, or everybody with **Clear batch**; both ask first.
 * **Download list** saves the batch as a spreadsheet. **Download list**, **Save as a
 * group**, and **Clear batch** sit in one row. After an add the focus moves to the
 * line saying what it did. A change to the batch of a
 * scheduled email takes it back to the drafts, and the screen says so. A DART
 * leader's email goes to one DART only: the DART filter gives way to that DART,
 * named as a fixed value. While that leader's profile names no DART, nobody can be
 * added, and the card says so, naming the leader, in place of the filters.
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
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterValues, Option } from '@/portal/reports/types';
import { DROP_ORDER } from './dropOrder';
import { AddGroupButton } from './AddGroupButton';
import {
  batchCsvUrl,
  givenFilters,
  useAddToBatch,
  useBatch,
  useClearBatch,
  useRemoveFromBatch,
} from './api';
import { SaveGroupButton } from './SaveGroupButton';
import { addSentence, batchSentence, kindLabel, people } from './status';

/** The member list's filters, less any only a subscription offers, with a short search hint. */
export const FILTER_FIELDS = listFilters(REPORTS.members).map((field) =>
  field.key === 'search' ? { ...field, placeholder: 'Name or email' } : field,
);

/** The filters of an email limited to one DART: every one but the DART's own. */
const DART_LIMITED_FIELDS = FILTER_FIELDS.filter((field) => field.key !== 'dart');

/**
 * How long Add to batch waits before it reads the filters: longer than the filter
 * bar's pause, so words typed just before the press have been applied.
 */
const ADD_SETTLE_MS = SEARCH_DEBOUNCE_MS + 100;

/** How many people the batch table shows before **Show all** is pressed. */
export const SHORT_LIST_LENGTH = 10;

/** What the screen says when a change to the batch took a scheduled email back to the drafts. */
export const BACK_TO_DRAFT_MESSAGE =
  'The recipients changed, so this email is back in your drafts. Press Send or Schedule again when it is ready.';

/** What the card says when a request fails without a message of its own. */
const FALLBACK_ERROR = 'That did not work. Try again.';

interface RecipientsCardProps {
  emailId: number;
  /** False once the email has started sending: the batch is then shown, not changed. */
  isEditable: boolean;
  /** True while the email waits to send, when any change to the batch unqueues it. */
  isQueued: boolean;
  /** The one DART a DART leader's email goes to; blank when it may go to anybody. */
  dartName: string;
  /** Why nobody can be added, naming the email's sender; blank when somebody can. */
  senderNotice: string;
}

/** The DARTs as the filter bar's DART choices, by id. */
export function useDartOptions(): Record<string, Option[]> {
  const darts = useDarts();
  return useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
    }),
    [darts.data],
  );
}

/** The batch: build it with the filters, read it, and change it. */
export function RecipientsCard({
  emailId,
  isEditable,
  isQueued,
  dartName,
  senderNotice,
}: RecipientsCardProps): JSX.Element {
  const [filters, setFilters] = useState<FilterValues>({});
  const [lastAdd, setLastAdd] = useState<BulkEmailAddResult | null>(null);
  const [search, setSearch] = useState('');
  const [isShowingAll, setIsShowingAll] = useState(false);
  const [isSettling, setIsSettling] = useState(false);
  const toast = useToast();

  const dartOptions = useDartOptions();

  const batch = useBatch(emailId);
  const add = useAddToBatch(emailId);
  const remove = useRemoveFromBatch(emailId);
  const clear = useClearBatch(emailId);
  const addRef = useRef<HTMLButtonElement>(null);
  const resultRef = useRef<HTMLParagraphElement>(null);

  // The line saying what an add did takes the focus, so a keyboard or screen reader
  // user hears it and carries on from it, rather than from the top of the page.
  useEffect(() => {
    if (lastAdd !== null) resultRef.current?.focus();
  }, [lastAdd]);

  // The filters as last applied, read by an add once the bar has settled.
  const filtersRef = useRef(filters);
  const addTimer = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (addTimer.current !== null) window.clearTimeout(addTimer.current);
    },
    [],
  );

  /** Say so when a change took a scheduled email back to the drafts. */
  const afterChange = (): void => {
    if (isQueued) toast.show(BACK_TO_DRAFT_MESSAGE, 'info');
  };

  const handleFilterChange = (next: FilterValues): void => {
    filtersRef.current = next;
    setFilters(next);
  };

  // A search typed just before the press applies after a short pause, so the add
  // waits out that pause; otherwise it would add whoever the old filters chose.
  const handleAdd = (): void => {
    setLastAdd(null);
    setIsSettling(true);
    addTimer.current = window.setTimeout(() => {
      addTimer.current = null;
      setIsSettling(false);
      add.mutate(filtersRef.current, {
        onSuccess: (result) => {
          setLastAdd(result);
          afterChange();
        },
        // The button was off while it worked, which took the focus away from it; a
        // refused add puts it back there, beside the reason.
        onError: () => window.setTimeout(() => addRef.current?.focus(), 0),
      });
    }, ADD_SETTLE_MS);
  };

  const handleRemove = isEditable
    ? (rowId: number): Promise<unknown> => remove.mutateAsync(rowId).then(afterChange)
    : undefined;

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setSearch(event.target.value);
  };

  const failure = add.error ?? remove.error ?? clear.error;
  const count = batch.data?.count ?? 0;

  return (
    <Card title="1. Who gets it" className="bulk-email__card">
      {isEditable ? (
        <p className="muted">
          The people you add make up the batch: the list this email goes to. Choose people with the
          filters, then press <strong>Add to batch</strong>. Add as many groups as you like: nobody
          is added twice.
        </p>
      ) : null}
      {isEditable && senderNotice !== '' ? (
        <p className="bulk-email__notice" role="status">
          {senderNotice}
        </p>
      ) : null}
      {isEditable && senderNotice === '' ? (
        <div className="stack">
          {dartName === '' ? null : (
            <p>
              Sending to the <strong>{dartName} DART</strong>. The filters choose people in that
              DART only.
            </p>
          )}
          <FilterBar
            fields={dartName === '' ? FILTER_FIELDS : DART_LIMITED_FIELDS}
            values={filters}
            onChange={handleFilterChange}
            options={dartOptions}
            label="Choose people to add"
          />
          <div className="stack-tight">
            <div className="cluster">
              <Button ref={addRef} onClick={handleAdd} disabled={add.isPending || isSettling}>
                {add.isPending || isSettling ? 'Adding…' : 'Add to batch'}
              </Button>
              <AddGroupButton
                emailId={emailId}
                onAdded={(result) => {
                  setLastAdd(result);
                  afterChange();
                }}
              />
            </div>
            {Object.keys(givenFilters(filters)).length > 0 ? null : (
              <p className="muted">
                {dartName === ''
                  ? 'With no filters chosen, this adds every member and friend.'
                  : `With no filters chosen, this adds every member and friend of the ${dartName} DART.`}
              </p>
            )}
          </div>
          {lastAdd === null ? null : (
            <p ref={resultRef} role="status" tabIndex={-1}>
              {addSentence(lastAdd)}
            </p>
          )}
        </div>
      ) : null}

      {failure === null ? null : (
        <p className="field__error" role="alert">
          {addComplaint(failure)}
        </p>
      )}

      {batch.data !== undefined && count > 0 ? (
        <p>
          <strong>{batchSentence(batch.data.receiving, batch.data.skipped)}</strong>
        </p>
      ) : null}

      {count > 0 ? (
        <div className="cluster bulk-email__batch-actions">
          <a className="button button--quiet button--small" href={batchCsvUrl(emailId)} download>
            Download list
          </a>
          <SaveGroupButton emailId={emailId} />
          {isEditable ? (
            <ConfirmButton
              label="Clear batch"
              variant="quiet"
              small
              choices={[
                {
                  label: 'Clear the batch',
                  variant: 'danger',
                  onChoose: () => clear.mutateAsync().then(afterChange),
                },
              ]}
            >
              <p>This takes all {people(count)} out of the batch. The message is kept.</p>
            </ConfirmButton>
          ) : null}
        </div>
      ) : null}

      {batch.isError ? (
        <p className="field__error" role="alert">
          The batch could not be loaded.
        </p>
      ) : (
        <BatchTable
          batch={batch.data}
          isLoading={batch.isLoading}
          search={search}
          isShowingAll={isShowingAll}
          onSearchChange={handleSearchChange}
          onShowAll={() => setIsShowingAll(true)}
          onRemove={handleRemove}
        />
      )}
    </Card>
  );
}

interface BatchTableProps {
  batch: BulkEmailBatch | undefined;
  isLoading: boolean;
  search: string;
  isShowingAll: boolean;
  onSearchChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onShowAll: () => void;
  /** Takes one person out; left out when the batch can no longer change. */
  onRemove?: (rowId: number) => Promise<unknown>;
}

/** The count sentence, a search box, and one line per person in the batch. */
function BatchTable({
  batch,
  isLoading,
  search,
  isShowingAll,
  onSearchChange: handleSearchChange,
  onShowAll: handleShowAll,
  onRemove,
}: BatchTableProps): JSX.Element {
  const labels = useMemo(
    () => new Map((batch?.adds ?? []).map((add) => [add.id, add.label])),
    [batch?.adds],
  );
  const matches = useMemo(() => matching(batch?.rows ?? [], search), [batch?.rows, search]);
  const isShort = !isShowingAll && search.trim() === '' && matches.length > SHORT_LIST_LENGTH;
  const rows = isShort ? matches.slice(0, SHORT_LIST_LENGTH) : matches;

  return (
    <div className="stack-tight">
      {batch !== undefined && batch.count > SHORT_LIST_LENGTH ? (
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
      />
      {isShort ? (
        <div className="cluster">
          <Button variant="quiet" onClick={handleShowAll}>
            {`Show all ${matches.length}`}
          </Button>
        </div>
      ) : null}
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

/**
 * The batch table's columns: the name, which tells the rows apart, and last the
 * trashcan column, which stays in sight on a phone, only while the batch can change.
 * The rows come in surname order from the server, and the columns sort on a press.
 * *Will receive?* wraps, so a skip reason is read whole, and stays in sight; *Chosen
 * by*, the DART, the kind, then the address give way when the table would not fit its
 * card.
 */
export function batchColumns(
  labels: Map<number, string>,
  onRemove: ((rowId: number) => Promise<unknown>) | undefined,
): Column<BulkEmailBatchRow>[] {
  const name: Column<BulkEmailBatchRow> = {
    key: 'name',
    header: 'Name',
    minWidth: '12rem',
    isIdentity: true,
    render: (row) => row.name,
    sortValue: (row) => row.name,
  };
  const delivery: Column<BulkEmailBatchRow>[] = [
    {
      key: 'email',
      header: 'Email',
      minWidth: '13rem',
      dropOrder: DROP_ORDER.address,
      render: (row) => row.email,
      sortValue: (row) => row.email,
    },
    {
      key: 'will_receive',
      header: 'Will receive?',
      width: '11rem',
      wrap: true,
      keepInSight: true,
      render: (row) => <WillReceive row={row} />,
      sortValue: (row) => (row.will_receive ? '' : row.reason),
    },
  ];
  const remove: Column<BulkEmailBatchRow>[] =
    onRemove === undefined
      ? []
      : [
          {
            key: 'remove',
            header: 'Remove',
            isActions: true,
            render: (row) => (
              <DeleteButton
                label={`Remove ${row.name || row.email} from the batch`}
                confirmLabel="Remove"
                onDelete={() => onRemove(row.id)}
              />
            ),
          },
        ];
  const details: Column<BulkEmailBatchRow>[] = [
    {
      key: 'kind',
      header: 'Kind',
      width: '5.5rem',
      dropOrder: DROP_ORDER.kind,
      render: (row) => kindLabel(row.kind),
      sortValue: (row) => row.kind,
    },
    {
      key: 'dart',
      header: 'DART',
      width: '8rem',
      dropOrder: DROP_ORDER.dart,
      render: (row) => row.dart_name || '—',
      sortValue: (row) => row.dart_name,
    },
    {
      key: 'chosen_by',
      header: 'Chosen by',
      minWidth: '10rem',
      dropOrder: DROP_ORDER.chosenBy,
      render: (row) => (row.added_by === null ? '—' : (labels.get(row.added_by) ?? '—')),
    },
  ];
  return [name, ...remove, ...delivery, ...details];
}

/** A dot and *Yes*, or a dot and the reason the person is skipped. */
function WillReceive({ row }: { row: BulkEmailBatchRow }): JSX.Element {
  const words = row.will_receive ? 'Yes' : row.reason;
  return (
    <span className="bulk-email__will-receive">
      <StatusDot tone={row.will_receive ? 'current' : 'none'} label={words} />
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
