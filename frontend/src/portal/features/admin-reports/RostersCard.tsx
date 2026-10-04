/**
 * The DART rosters card of `/admin/reports`: each active DART, how many of its
 * people receive its roster, when the last one went, and a button that sends
 * every roster now, whatever the date.  A roster lists the DART's members and
 * friends alike, with a Kind column.
 *
 * Who receives a DART's roster is checked on the DART itself, under **DARTs**.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { Roster } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { useRosters, useSendRosters } from '@/portal/reports/api';
import { ReportRunOutcome } from './ReportRunOutcome';

/** The DART tells the rows apart; the count and the date keep their widths. */
const COLUMNS: Column<Roster>[] = [
  {
    key: 'name',
    header: 'DART',
    minWidth: '12rem',
    isIdentity: true,
    render: (row) => row.name,
    sortValue: (row) => row.name,
  },
  {
    key: 'roster_recipients',
    header: 'Recipients',
    width: '7rem',
    numeric: true,
    render: (row) => row.roster_recipients,
    sortValue: (row) => row.roster_recipients,
  },
  {
    key: 'roster_sent_at',
    header: 'Last sent',
    width: '7rem',
    noWrap: true,
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
      title="DART rosters"
      footer={
        <>
          <Button onClick={handleSend} disabled={send.isPending}>
            {send.isPending ? 'Sending…' : 'Send rosters now'}
          </Button>
          <PracticeRunCheckbox checked={dryRun} onChange={handleDryRunChange} task="DART rosters" />
        </>
      }
    >
      <p className="muted">
        Early each month, each DART&rsquo;s roster goes out as a PDF to the people checked to
        receive it. It lists the DART&rsquo;s members and friends.
      </p>

      {rosters.isError ? (
        <p className="field__error" role="alert">
          {rosters.error instanceof Error
            ? rosters.error.message
            : "The rosters didn't load. Try again in a moment."}
        </p>
      ) : (
        <DataTable
          singleLine
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
