/**
 * The people a search on the compose screen matches, before anybody is added: a
 * sentence with how many, and a table of them a page at a time, each with whether
 * they would receive the email or why not, as the recipient list says it.
 */
import type { JSX } from 'react';

import type { BulkEmailMatch, Paginated } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { StatusDot } from '@/portal/components/StatusDot';
import { MATCHES_PAGE_SIZE } from './api';
import { DROP_ORDER } from './dropOrder';
import { kindLabel, people } from './status';

interface SearchResultsProps {
  /** The page of matches shown; undefined until the first page arrives. */
  matches: Paginated<BulkEmailMatch> | undefined;
  isLoading: boolean;
  /** True when no filter carries a value, so the search matches everybody. */
  isUnfiltered: boolean;
  /** The one DART a DART leader's email goes to; blank when it may go to anybody. */
  dartName: string;
  page: number;
  onPageChange: (page: number) => void;
}

/** The count sentence and the table of matched people, paged. */
export function SearchResults({
  matches,
  isLoading,
  isUnfiltered,
  dartName,
  page,
  onPageChange: handlePageChange,
}: SearchResultsProps): JSX.Element {
  const count = matches?.count ?? 0;
  return (
    <div className="stack-tight">
      {matches === undefined ? null : (
        <p aria-live="polite">
          <strong>{matchSentence(count, isUnfiltered, dartName)}</strong>
        </p>
      )}
      <DataTable
        singleLine
        columns={MATCH_COLUMNS}
        rows={matches?.results ?? []}
        rowKey={(row) => row.user_id}
        caption={`People these filters match: ${people(count)}`}
        emptyTitle="Nobody matches these filters"
        emptyDescription="Change the filters to find the people to add."
        isLoading={isLoading}
        pagination={{
          page,
          pageSize: MATCHES_PAGE_SIZE,
          count,
          onPageChange: handlePageChange,
          label: 'Pages of matching people',
        }}
      />
    </div>
  );
}

/**
 * What a search comes to: `12 people match these filters.`, or, with no filter
 * chosen, that it takes in every member and friend (of the DART, for a DART leader).
 *
 * @param count how many people the search matches.
 * @param isUnfiltered true when no filter carries a value.
 * @param dartName the DART a leader's email is held to, or blank.
 */
export function matchSentence(count: number, isUnfiltered: boolean, dartName: string): string {
  if (count === 0) return 'Nobody matches these filters.';
  if (isUnfiltered) {
    const everybody =
      dartName === ''
        ? 'every member and friend'
        : `every member and friend of the ${dartName} DART`;
    return `With no filters chosen, this is ${everybody}: ${people(count)}.`;
  }
  return count === 1 ? '1 person matches these filters.' : `${count} people match these filters.`;
}

/**
 * The matches table's columns: the name, which tells the rows apart, then *Will
 * receive?*, which wraps so a skip reason is read whole and stays in sight; the
 * address, the kind, then the DART give way when the table would not fit its card.
 */
const MATCH_COLUMNS: Column<BulkEmailMatch>[] = [
  {
    key: 'name',
    header: 'Name',
    minWidth: '12rem',
    isIdentity: true,
    render: (row) => row.name,
  },
  {
    key: 'email',
    header: 'Email',
    minWidth: '13rem',
    dropOrder: DROP_ORDER.address,
    render: (row) => row.email,
  },
  {
    key: 'will_receive',
    header: 'Will receive?',
    width: '11rem',
    wrap: true,
    keepInSight: true,
    render: (row) => <WillReceive row={row} />,
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

/** Whether one person receives a copy, and why not. */
interface Receiving {
  will_receive: boolean;
  reason: string;
}

/** A dot and *Yes*, or a dot and the reason the person is skipped. */
export function WillReceive({ row }: { row: Receiving }): JSX.Element {
  const words = row.will_receive ? 'Yes' : row.reason;
  return (
    <span className="bulk-email__will-receive">
      <StatusDot tone={row.will_receive ? 'current' : 'none'} label={words} />
    </span>
  );
}
