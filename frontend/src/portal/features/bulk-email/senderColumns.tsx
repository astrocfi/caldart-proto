/**
 * The From and DART columns the Drafts and scheduled and Sent lists show CalDART
 * management, who sees every sender's emails. A DART leader sees only their own, so
 * their lists leave both out. Both give way to the columns that matter more when the
 * table would not fit its card.
 */
import type { BulkEmailSummary } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DROP_ORDER } from './dropOrder';

/** Who wrote each email, and the DART a DART leader's email goes to. */
const SENDER_COLUMNS: Column<BulkEmailSummary>[] = [
  {
    key: 'sender',
    header: 'From',
    width: '7rem',
    dropOrder: DROP_ORDER.from,
    render: (row) => row.sender || '—',
    sortValue: (row) => row.sender,
  },
  {
    key: 'dart_name',
    header: 'DART',
    width: '7rem',
    dropOrder: DROP_ORDER.dart,
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
