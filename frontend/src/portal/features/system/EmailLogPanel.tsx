/**
 * The email log panel of `/portal/system`: the newest fifty messages the
 * system has tried to send, filtered by purpose or by who they went to.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { EmailLogEntry } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { useDebounced } from '@/portal/components/useDebounced';
import { useEmailLog } from './api';
import { PURPOSE_LABELS, purposeLabel } from './labels';

const COLUMNS: Column<EmailLogEntry>[] = [
  {
    key: 'sent_at',
    header: 'Sent',
    render: (row) => <DateText value={row.sent_at} withTime />,
    sortValue: (row) => row.sent_at,
  },
  {
    key: 'purpose',
    header: 'Purpose',
    render: (row) => purposeLabel(row.purpose),
    sortValue: (row) => row.purpose,
  },
  {
    key: 'to',
    header: 'To',
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
    sortValue: (row) => row.user_name || row.to_email,
  },
  {
    key: 'status',
    header: 'Status',
    render: (row) => (row.status === 'sent' ? 'Sent' : `Failed: ${row.error}`),
    sortValue: (row) => row.status,
  },
  {
    key: 'attachments',
    header: 'Attachments',
    render: (row) => (row.attachments === '' ? <span className="muted">—</span> : row.attachments),
  },
];

/** The most recent emails the system has tried to send, with a purpose filter and search. */
export function EmailLogPanel(): JSX.Element {
  const [purpose, setPurpose] = useState<string>('all');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounced(search);
  const log = useEmailLog(purpose, debouncedSearch);

  const handlePurposeChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    setPurpose(event.target.value);
  };

  return (
    <Card eyebrow="Operations" title="Email log">
      <DataTable
        columns={COLUMNS}
        rows={log.data?.results ?? []}
        rowKey={(row) => row.id}
        isLoading={log.isPending}
        caption={log.data ? `${log.data.count} email${log.data.count === 1 ? '' : 's'}` : undefined}
        emptyTitle="No emails sent yet"
        emptyDescription="Nothing has gone out yet, or nothing matches these filters."
        filters={
          <>
            <Field label="Purpose">
              {(props) => (
                <select {...props} value={purpose} onChange={handlePurposeChange}>
                  <option value="all">All purposes</option>
                  {Object.keys(PURPOSE_LABELS).map((key) => (
                    <option key={key} value={key}>
                      {PURPOSE_LABELS[key]}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Search">
              {(props) => (
                <input
                  {...props}
                  type="search"
                  autoComplete="off"
                  placeholder="Name or address"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              )}
            </Field>
          </>
        }
      />
    </Card>
  );
}
