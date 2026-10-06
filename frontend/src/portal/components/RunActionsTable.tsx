/**
 * The block every scheduled run shows for its result: the heading, the
 * caller's summary of what happened, and the table of every action behind
 * it — one row per email sent or charge taken, so "who did this actually
 * reach?" never needs a shell.  The renewals, reminders, scheduled-reports,
 * statements, bounces, and bulk email sender panels of the Scheduled tasks page
 * (`/portal/system/scheduled`) use it, and so does the DART rosters card of
 * `/admin/reports`.
 *
 * A column that is empty in every row, such as When and Amount for a run of rosters, is
 * left out, so the table shows only what the run says.  The table keeps each row on one
 * line.  Who an action reached tells the rows apart
 * and stays pinned while a phone scrolls the table; what was done and the detail, such
 * as the report or the DART, stay in sight beside it, so a phone still says which
 * reminder goes to whom; the date, then the amount, give way on a narrow screen.
 */
import type { JSX, ReactNode } from 'react';

import type { RunAction } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { identityFirst } from '@/portal/components/tableFit';

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
  /**
   * Whether the actions carry a date and an amount.  A run that only sends
   * emails about no particular day, such as the bulk email sender, passes false to
   * leave the When and Amount columns out.
   */
  hasWhenAndAmount?: boolean;
  /** The heading over the table, in place of `actionsHeading`'s. */
  heading?: string;
  /** The table's caption, in place of the count of actions. */
  caption?: string;
  /** What an empty table says, in place of *Nothing was due*. */
  emptyTitle?: string;
  /** A line under an empty table's title. */
  emptyDescription?: string;
}

/** What the actions table's columns are built from. */
export interface RunActionColumnsOptions {
  actions: readonly RunAction[];
  kindLabel: (kind: string) => string;
  detailHeader?: string;
  hasWhenAndAmount?: boolean;
}

/**
 * The actions table's columns: Who and What, the detail when the caller names one and a
 * row fills it, then When and Amount when a row fills them.  Who is the identifying
 * column; What and the detail stay in sight on a phone; When gives way first, then
 * Amount.
 */
export function runActionColumns({
  actions,
  kindLabel,
  detailHeader,
  hasWhenAndAmount = true,
}: RunActionColumnsOptions): Column<RunAction>[] {
  // A column no row fills is left out; an empty table draws no headings at all.
  const hasDetail = actions.some((row) => row.detail !== '');
  const hasWhen = actions.some((row) => row.on !== null);
  const hasAmount = actions.some((row) => row.amount_cents !== null);
  const detail: Column<RunAction>[] =
    detailHeader === undefined || !hasDetail
      ? []
      : [
          {
            key: 'detail',
            header: detailHeader,
            minWidth: '10rem',
            wrap: true,
            keepInSight: true,
            narrowWidth: '8rem',
            render: (row) => row.detail,
          },
        ];
  const whenAndAmount: Column<RunAction>[] = [
    ...(hasWhenAndAmount && hasWhen
      ? [
          {
            key: 'on',
            header: 'When',
            width: '7rem',
            noWrap: true,
            dropOrder: 1,
            render: (row: RunAction) => <DateText value={row.on} />,
          },
        ]
      : []),
    ...(hasWhenAndAmount && hasAmount
      ? [
          {
            key: 'amount_cents',
            header: 'Amount',
            width: '6rem',
            dropOrder: 2,
            numeric: true,
            render: (row: RunAction) => <Money cents={row.amount_cents} />,
          },
        ]
      : []),
  ];
  const columns: Column<RunAction>[] = [
    {
      key: 'kind',
      header: 'What',
      minWidth: '9rem',
      keepInSight: true,
      narrowWidth: '8rem',
      render: (row) => kindLabel(row.kind),
    },
    {
      key: 'member',
      header: 'Who',
      minWidth: '12rem',
      isIdentity: true,
      // An action about an address nobody is named for, such as a bounce no sent
      // email matched, shows the address alone.
      render: (row) =>
        row.member === '' ? (
          row.email
        ) : (
          <>
            {row.member}
            <span className="muted"> · {row.email}</span>
          </>
        ),
    },
    ...detail,
    ...whenAndAmount,
  ];
  // Who leads, pinned as a phone scrolls the table, with What beside it.
  return identityFirst(columns);
}

/** A run's heading, its caller-supplied summary, and the actions behind it. */
export function RunActionsTable({
  actions,
  dryRun,
  kindLabel,
  detailHeader,
  summary,
  hasWhenAndAmount = true,
  heading,
  caption,
  emptyTitle = 'Nothing was due',
  emptyDescription,
}: RunActionsTableProps): JSX.Element {
  const columns = runActionColumns({ actions, kindLabel, detailHeader, hasWhenAndAmount });
  return (
    <div className="run-actions stack-tight">
      <h3>{heading ?? actionsHeading(dryRun)}</h3>
      {summary}
      <DataTable
        singleLine
        columns={columns}
        rows={actions}
        rowKey={(row) => `${row.kind}-${row.member}-${row.email}-${row.on ?? ''}-${row.detail}`}
        caption={caption ?? `${actions.length} action${actions.length === 1 ? '' : 's'}`}
        emptyTitle={emptyTitle}
        emptyDescription={emptyDescription}
      />
    </div>
  );
}
