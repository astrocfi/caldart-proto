/**
 * The email log, the body of `/portal/system/emails`: every message the system has tried
 * to send, a page at a time, newest first.
 *
 * The filters are the `emails` report's own, drawn by the shared `FilterBar`
 * from `REPORTS.emails`, and they live in the address beside the order and the
 * page, so a filtered view of the log is a link.  The export links download the
 * same rows as the `emails` report, carrying the filters, the order and the
 * columns chosen for the export, but every page rather than the one on screen.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { EmailLogEntry, EmailStatus } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { FilterBar } from '@/portal/components/FilterBar';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { reportExportUrl, useReportColumns } from '@/portal/reports/api';
import { listFilters, REPORTS } from '@/portal/reports/definitions';
import type { FilterValues } from '@/portal/reports/types';
import { EMAIL_LOG_PAGE_SIZE, useEmailLog, useEmailPurposes } from './api';

/** The filters the panel draws: the email log report's own. */
const FILTER_FIELDS = listFilters(REPORTS.emails);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/** The most recent send first, as the server orders the log by default. */
const DEFAULT_ORDERING = '-sent_at';

/** What the Status column reads for each status: a refusal carries its error. */
const STATUS_TEXT: Record<EmailStatus, (row: EmailLogEntry) => string> = {
  sent: () => 'Sent',
  failed: (row) => `Failed: ${row.error}`,
  bounced: () => 'Bounced',
};

const COLUMNS: Column<EmailLogEntry>[] = [
  {
    key: 'sent_at',
    header: 'Sent',
    render: (row) => <DateText value={row.sent_at} withTime />,
  },
  {
    key: 'purpose',
    header: 'Purpose',
    sortable: false,
    render: (row) => row.purpose_label,
  },
  {
    key: 'to',
    header: 'To',
    sortable: false,
    render: (row) => (
      <>
        {row.user_name ? (
          <>
            {row.user_name}
            <span className="muted"> · </span>
          </>
        ) : null}
        <span className="mono">{row.to_email}</span>
      </>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    sortable: false,
    render: (row) => STATUS_TEXT[row.status](row),
  },
  {
    key: 'bounce',
    header: 'Bounce',
    sortable: false,
    render: (row) =>
      row.bounced_at === null ? (
        <span className="muted">—</span>
      ) : (
        <>
          <DateText value={row.bounced_at} />
          <span className="muted"> · {row.bounce_detail}</span>
        </>
      ),
  },
  {
    key: 'attachments',
    header: 'Attachments',
    sortable: false,
    render: (row) => (row.attachments === '' ? <span className="muted">—</span> : row.attachments),
  },
];

/** The email log: filtered, paged, sorted by when each message went, and downloadable. */
export function EmailLogPanel(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage, sort, setSort: handleSortChange } = position;

  const log = useEmailLog({ filters, ordering, page });
  useFirstPageWhenMissing(position, log.error);

  const purposes = useEmailPurposes();
  const purposeOptions = useMemo(() => ({ purpose: purposes.data ?? [] }), [purposes.data]);

  const registry = useReportColumns('emails');
  const reportColumns = useMemo(() => registry.data ?? [], [registry.data]);
  // Null means "whatever the registry calls default": the chooser has not been
  // touched, so it must follow a registry that is still loading.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const chosenKeys = chosen ?? defaultColumnKeys(reportColumns);
  const exportParams = { ...filters, ordering, columns: chosenKeys };

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
  };

  const handleColumnChange = (next: string[]): void => {
    setChosen(next);
  };

  const count = log.data?.count ?? 0;
  const rows = log.data?.results ?? [];
  const firstRow = count === 0 ? 0 : (page - 1) * EMAIL_LOG_PAGE_SIZE + 1;
  const lastRow = (page - 1) * EMAIL_LOG_PAGE_SIZE + rows.length;

  return (
    <Card>
      {log.isError ? (
        <p className="field__error" role="alert">
          {log.error instanceof Error ? log.error.message : 'Could not read the email log.'}
        </p>
      ) : null}

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.id}
        isLoading={log.isPending}
        caption={log.data ? `${count} email${count === 1 ? '' : 's'}` : undefined}
        onSortChange={handleSortChange}
        sort={sort}
        exportCsvUrl={reportExportUrl('emails', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('emails', 'pdf', exportParams)}
        emptyTitle="No emails sent yet"
        emptyDescription="Nothing has gone out yet, or nothing matches these filters."
        filters={
          <>
            <FilterBar
              fields={FILTER_FIELDS}
              values={filters}
              onChange={handleFilterChange}
              options={purposeOptions}
              label="Filter the email log"
            />
            {registry.isError ? (
              <p className="muted">
                The columns could not be loaded; the downloads carry the default columns.
              </p>
            ) : reportColumns.length > 0 ? (
              <ColumnChooser
                report="emails"
                columns={reportColumns}
                chosen={chosenKeys}
                onChange={handleColumnChange}
                legend="Columns to export"
              />
            ) : null}
          </>
        }
      />

      {count > EMAIL_LOG_PAGE_SIZE ? (
        <div className="cluster card__footer">
          <p className="muted">
            Showing {firstRow}–{lastRow} of {count}
          </p>
          <Button
            variant="quiet"
            small
            disabled={!log.data?.previous}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="quiet"
            small
            disabled={!log.data?.next}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
