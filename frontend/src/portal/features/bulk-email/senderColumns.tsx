/**
 * The From and DART columns the Drafts & scheduled and Sent lists show CalDART
 * management, who sees every sender's emails. A DART leader sees only their own, so
 * their lists leave both out.
 */
import type { BulkEmailSummary } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';

/** Who wrote each email, and the DART a DART leader's email goes to. */
const SENDER_COLUMNS: Column<BulkEmailSummary>[] = [
  {
    key: 'sender',
    header: 'From',
    width: '7rem',
    render: (row) => row.sender || '—',
    sortValue: (row) => row.sender,
  },
  {
    key: 'dart_name',
    header: 'DART',
    width: '7rem',
    render: (row) => row.dart_name || '—',
    sortValue: (row) => row.dart_name,
  },
];

/**
 * `columns` with the From and DART columns just before Status, for CalDART management.
 *
 * @param columns a list's columns, one of them keyed `status`.
 * @param isManagement true when the viewer is CalDART management.
 * @returns the columns to show.
 */
export function withSenderColumns(
  columns: Column<BulkEmailSummary>[],
  isManagement: boolean,
): Column<BulkEmailSummary>[] {
  if (!isManagement) return columns;
  const at = columns.findIndex((column) => column.key === 'status');
  return [...columns.slice(0, at), ...SENDER_COLUMNS, ...columns.slice(at)];
}
