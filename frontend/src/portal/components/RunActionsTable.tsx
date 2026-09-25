/**
 * The block every scheduled run shows for its result: the heading, the
 * caller's summary of what happened, and the table of every action behind
 * it — one row per email sent or charge taken, so "who did this actually
 * reach?" never needs a shell.  The renewals, reminders and scheduled-reports
 * panels of `/portal/system` use it, and so does the DART rosters card of
 * `/admin/reports`.
 */
import type { JSX, ReactNode } from 'react';

import type { RunAction } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';

/** The heading over the actions table: what a rehearsal would do, or what a real run did. */
export function actionsHeading(dryRun: boolean): string {
  return dryRun ? 'What this run would do' : 'What this run did';
}

interface RunActionsTableProps {
  actions: RunAction[];
  dryRun: boolean;
  /** How a run's own `kind` slug reads; the two scans name their kinds differently. */
  kindLabel: (kind: string) => string;
  /**
   * The heading of a column showing each action's `detail`, for a run whose
   * actions say more than who they reached (the report sent, the DART whose
   * roster went out).  Without it the column is left out.
   */
  detailHeader?: string;
  /**
   * The counts sentence, the skip breakdown and the failed line, rendered
   * between the heading and the table.  Left out when the caller has nothing
   * to report yet.
   */
  summary?: ReactNode;
}

/** A run's heading, its caller-supplied summary, and the actions behind it. */
export function RunActionsTable({
  actions,
  dryRun,
  kindLabel,
  detailHeader,
  summary,
}: RunActionsTableProps): JSX.Element {
  const detail: Column<RunAction>[] =
    detailHeader === undefined
      ? []
      : [{ key: 'detail', header: detailHeader, render: (row) => row.detail }];
  const columns: Column<RunAction>[] = [
    { key: 'kind', header: 'What', render: (row) => kindLabel(row.kind) },
    {
      key: 'member',
      header: 'Who',
      render: (row) => (
        <>
          {row.member}
          <span className="muted"> · {row.email}</span>
        </>
      ),
    },
    ...detail,
    { key: 'on', header: 'When', render: (row) => <DateText value={row.on} /> },
    {
      key: 'amount_cents',
      header: 'Amount',
      numeric: true,
      render: (row) => <Money cents={row.amount_cents} />,
    },
  ];

  return (
    <div className="run-actions">
      <h3>{actionsHeading(dryRun)}</h3>
      {summary}
      <DataTable
        columns={columns}
        rows={actions}
        rowKey={(row) => `${row.kind}-${row.email}-${row.on ?? ''}-${row.detail}`}
        caption={`${actions.length} action${actions.length === 1 ? '' : 's'}`}
        emptyTitle="Nothing was due"
      />
    </div>
  );
}
