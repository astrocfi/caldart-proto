/**
 * The actions table shared by the renewals and reminders panels of
 * `/portal/system`: one row per email sent or charge taken behind a run's
 * summary counts, so "who did this actually reach?" never needs a shell.
 */
import type { JSX } from 'react';

import type { RunAction } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';

/** The heading over the actions table: what a rehearsal would do, or what a real run did. */
export function actionsHeading(dryRun: boolean): string {
  return dryRun ? 'What a live run would do' : 'What this run did';
}

interface RunActionsTableProps {
  actions: RunAction[];
  dryRun: boolean;
  /** How a run's own `kind` slug reads; the two scans name their kinds differently. */
  kindLabel: (kind: string) => string;
}

/** What a scan did, or would do: the kind, who it reached, when, and how much. */
export function RunActionsTable({ actions, dryRun, kindLabel }: RunActionsTableProps): JSX.Element {
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
    { key: 'on', header: 'When', render: (row) => <DateText value={row.on} /> },
    {
      key: 'amount_cents',
      header: 'Amount',
      numeric: true,
      render: (row) => <Money cents={row.amount_cents} />,
    },
  ];

  return (
    <>
      <h3>{actionsHeading(dryRun)}</h3>
      <DataTable
        columns={columns}
        rows={actions}
        rowKey={(row) => `${row.kind}-${row.email}-${row.on ?? ''}-${row.detail}`}
        caption={`${actions.length} action${actions.length === 1 ? '' : 's'}`}
        emptyTitle="Nothing was due"
      />
    </>
  );
}
