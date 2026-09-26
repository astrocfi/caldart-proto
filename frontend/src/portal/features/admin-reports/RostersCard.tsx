/**
 * The DART rosters card of `/admin/reports`: each active DART, how many of its
 * people receive its roster, when the last one went, and a button that sends
 * every roster now, whatever the date.  A roster lists the DART's members and
 * friends alike, with a Kind column.
 *
 * Who receives a DART's roster is ticked on the DART itself, under **DARTs**.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { Roster } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { useRosters, useSendRosters } from '@/portal/reports/api';
import { ReportRunOutcome } from './ReportRunOutcome';

const COLUMNS: Column<Roster>[] = [
  { key: 'name', header: 'DART', render: (row) => row.name, sortValue: (row) => row.name },
  {
    key: 'roster_recipients',
    header: 'Recipients',
    numeric: true,
    render: (row) => row.roster_recipients,
    sortValue: (row) => row.roster_recipients,
  },
  {
    key: 'roster_sent_at',
    header: 'Last sent',
    render: (row) => <DateText value={row.roster_sent_at} />,
    sortValue: (row) => row.roster_sent_at,
  },
];

/** The rosters table and the button that sends them now, or rehearses it. */
export function RostersCard(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const rosters = useRosters();
  const send = useSendRosters();
  const rows = rosters.data ?? [];

  const handleSend = (): void => {
    setLastRunWasDry(dryRun);
    send.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card
      eyebrow="By email"
      title="DART rosters"
      footer={
        <>
          <Button onClick={handleSend} disabled={send.isPending}>
            {send.isPending ? 'Sending…' : 'Send rosters now'}
          </Button>
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
            Dry run (send nothing)
          </label>
        </>
      }
    >
      <p className="muted">
        Early each month every active DART&rsquo;s roster goes as a PDF to each of its people ticked
        to receive it who has an email address. A roster lists the DART&rsquo;s members and friends,
        its Kind column saying which each one is, and never a deactivated account.{' '}
        <strong>Send rosters now</strong> sends every one at once, whatever the date.
      </p>

      {rosters.isError ? (
        <p className="field__error" role="alert">
          {rosters.error instanceof Error
            ? rosters.error.message
            : 'The rosters could not be loaded.'}
        </p>
      ) : (
        <DataTable
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => row.dart_id}
          caption={`${rows.length} DART${rows.length === 1 ? '' : 's'}`}
          emptyTitle="No active DARTs"
          isLoading={rosters.isLoading}
        />
      )}

      {send.isSuccess ? <ReportRunOutcome result={send.data} dryRun={lastRunWasDry} /> : null}

      {send.isError ? (
        <p className="field__error" role="alert">
          {send.error instanceof Error ? send.error.message : 'The rosters were not sent.'}
        </p>
      ) : null}
    </Card>
  );
}
