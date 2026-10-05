/**
 * The DART rosters card of `/admin/reports`: each active DART, how many of its
 * people receive its roster, when the last one went, and a button that sends
 * every roster now, whatever the date.  Under the table sit the practice-run box, the
 * button it changes, and then what the last run did, in the order the Scheduled page
 * keeps, so the button never moves when a long result appears; while the box is checked
 * the button reads **Preview rosters**, and when a run ends the focus moves to its
 * result.  A roster lists the DART's members and friends alike, with a Kind column.
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
import { useFocusRunResult } from '@/portal/components/focus';
import { useRosters, useSendRosters } from '@/portal/reports/api';
import { ReportRunOutcome } from './ReportRunOutcome';
import './admin-reports.css';

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

/** The button's words: a preview while the practice-run box is checked, else a send. */
export function sendLabel(dryRun: boolean, isPending: boolean): string {
  if (dryRun) return isPending ? 'Previewing…' : 'Preview rosters';
  return isPending ? 'Sending…' : 'Send rosters now';
}

/** The rosters table and the button that sends them now, or rehearses it. */
export function RostersCard(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const rosters = useRosters();
  const send = useSendRosters();
  const rows = rosters.data ?? [];
  const resultRef = useFocusRunResult(send.isPending);

  const handleSend = (): void => {
    setLastRunWasDry(dryRun);
    send.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card title="DART rosters">
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

      <div className="cluster rosters__run">
        <PracticeRunCheckbox checked={dryRun} onChange={handleDryRunChange} task="DART rosters" />
        <Button onClick={handleSend} disabled={send.isPending}>
          {sendLabel(dryRun, send.isPending)}
        </Button>
      </div>

      <div ref={resultRef} className="rosters__result">
        {send.isSuccess ? <ReportRunOutcome result={send.data} dryRun={lastRunWasDry} /> : null}
        {send.isError ? (
          <p className="field__error" role="alert">
            {send.error instanceof Error ? send.error.message : 'The rosters were not sent.'}
          </p>
        ) : null}
      </div>
    </Card>
  );
}
