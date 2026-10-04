/**
 * The email log, the body of `/portal/system/emails`: every message the system has tried
 * to send, a page at a time, newest first.
 *
 * The filters are the `emails` report's own, drawn by the shared `FilterBar`
 * from `REPORTS.emails`, and they live in the address beside the order and the
 * page, so a filtered view of the log is a link.  The column chooser drives the
 * table and the two export links together, so the downloads carry the columns on
 * screen, for every page rather than the one shown.  A message that belongs to a
 * record, such as a copy of a bulk email, links to it.
 */
import { useMemo } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { EmailLogEntry, EmailStatus, ReportColumn } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { StatusDot } from '@/portal/components/StatusDot';
import type { StatusTone } from '@/portal/components/StatusDot';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { reportExportUrl } from '@/portal/reports/api';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterValues } from '@/portal/reports/types';
import { EMAIL_LOG_PAGE_SIZE, useEmailLog, useEmailPurposes } from './api';

/** The filters the panel draws: the email log report's own. */
const FILTER_FIELDS = listFilters(REPORTS.emails);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/** The most recent send first, as the server orders the log by default. */
const DEFAULT_ORDERING = '-sent_at';

/** The dot beside each status: green sent, red failed or bounced. */
const STATUS_TONE: Record<EmailStatus, StatusTone> = {
  sent: 'current',
  failed: 'expired',
  bounced: 'expired',
};

/** What the Status column reads for each status: a refusal carries its error. */
const STATUS_TEXT: Record<EmailStatus, (row: EmailLogEntry) => string> = {
  sent: () => 'Sent',
  failed: (row) => `Failed: ${row.error}`,
  bounced: () => 'Bounced',
};

/** A dash for a cell with nothing in it. */
const NOTHING = <span className="muted">—</span>;

/**
 * The email log report's columns, with its default ones checked, which the table shows
 * while the registry loads or if it cannot be read.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'sent_at', label: 'Sent', default: true },
  { key: 'purpose', label: 'Purpose', default: true },
  { key: 'to_email', label: 'To', default: true },
  { key: 'user_name', label: 'Name', default: true },
  { key: 'subject', label: 'Subject', default: true },
  { key: 'status', label: 'Status', default: true },
];

/**
 * How the table draws each column of the email log report.  The subject tells one
 * row from another; the columns the defaults leave out drop first on a narrow screen,
 * then the purpose, the name, and the address.  Only Sent sorts: it is the one order
 * the log takes.
 */
const CELLS: Record<string, ReportCell<EmailLogEntry>> = {
  sent_at: {
    ordering: 'sent_at',
    width: '12rem',
    noWrap: true,
    render: (row) => <DateText value={row.sent_at} withTime />,
  },
  purpose: {
    minWidth: '10rem',
    dropOrder: 5,
    // A copy of a bulk email leads to that email's page on Sent.
    render: (row) =>
      row.link === '' ? row.purpose_label : <Link to={row.link}>{row.purpose_label}</Link>,
  },
  to_email: { minWidth: '14rem', dropOrder: 7, render: (row) => row.to_email },
  user_name: {
    minWidth: '9rem',
    dropOrder: 6,
    render: (row) => (row.user_name === '' ? NOTHING : row.user_name),
  },
  subject: { minWidth: '14rem', isIdentity: true, render: (row) => row.subject },
  status: {
    minWidth: '7rem',
    keepInSight: true,
    render: (row) => (
      <StatusDot tone={STATUS_TONE[row.status]} label={STATUS_TEXT[row.status](row)} />
    ),
  },
  error: {
    minWidth: '12rem',
    dropOrder: 3,
    render: (row) => (row.error === '' ? NOTHING : row.error),
  },
  attachments: {
    minWidth: '12rem',
    dropOrder: 2,
    render: (row) => (row.attachments === '' ? NOTHING : row.attachments),
  },
  bounced_at: {
    width: '8rem',
    noWrap: true,
    dropOrder: 4,
    render: (row) => (row.bounced_at === null ? NOTHING : <DateText value={row.bounced_at} />),
  },
  bounce_detail: {
    minWidth: '12rem',
    dropOrder: 1,
    render: (row) => (row.bounce_detail === '' ? NOTHING : row.bounce_detail),
  },
};

/** The email log: filtered, paged, sorted by when each message went, and downloadable. */
export function EmailLogPanel(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage: handlePageChange, sort, setSort: handleSortChange } = position;

  const log = useEmailLog({ filters, ordering, page });
  useFirstPageWhenMissing(position, log.error);

  const purposes = useEmailPurposes();
  const purposeOptions = useMemo(() => ({ purpose: purposes.data ?? [] }), [purposes.data]);

  const choice = useColumnChoice('emails', FALLBACK_COLUMNS);
  const columns = reportTableColumns(choice.tableColumns, choice.tableChosen, CELLS, true);
  const exportParams = { ...filters, ordering, columns: choice.chosen };

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
  };

  const handleReset = (): void => {
    setFilters(clearedValues(FILTER_FIELDS, filters));
  };

  const count = log.data?.count ?? 0;
  const rows = log.data?.results ?? [];
  const isFiltered = FILTER_KEYS.some((key) => (filters[key] ?? '') !== '');

  return (
    <Card>
      {log.isError ? (
        <p className="field__error" role="alert">
          {log.error instanceof Error
            ? log.error.message
            : "The sent emails didn't load. Try again in a moment."}
        </p>
      ) : null}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        isLoading={log.isPending}
        caption={log.data ? `${count} email${count === 1 ? '' : 's'}` : undefined}
        label="Sent emails"
        onSortChange={handleSortChange}
        sort={sort}
        exportCsvUrl={reportExportUrl('emails', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('emails', 'pdf', exportParams)}
        emptyTitle={isFiltered ? 'No emails match these filters' : 'No emails sent yet'}
        emptyDescription={
          isFiltered ? 'Widen the dates, or reset the filters to see every email.' : undefined
        }
        emptyAction={
          isFiltered ? (
            <Button variant="secondary" onClick={handleReset}>
              Reset filters
            </Button>
          ) : undefined
        }
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={handleFilterChange}
            options={purposeOptions}
            label="Filter the email log"
          />
        }
        tools={<ColumnTools choice={choice} />}
        pagination={{
          page,
          pageSize: EMAIL_LOG_PAGE_SIZE,
          count,
          onPageChange: handlePageChange,
          label: 'Email log pages',
        }}
      />
    </Card>
  );
}
