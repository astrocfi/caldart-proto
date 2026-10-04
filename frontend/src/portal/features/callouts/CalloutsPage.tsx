/**
 * `/bulk-email/callouts`: every mission callout the signed-in sender may open, the
 * most recently sent first, one line each with its answers counted.
 *
 * CalDART management sees every callout; a DART leader the ones they sent and the ones
 * that went to their own DART. The subject opens the callout's answers. A callout is
 * written on the compose screen with **This is a mission callout** switched on.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { CalloutSummary } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusChip';
import { useCallouts } from './api';
import './callouts.css';
import { openLabel } from './labels';

/** Every callout, one line each. */
export function CalloutsPage(): JSX.Element {
  const callouts = useCallouts();
  const rows = callouts.data ?? [];

  return (
    <Page
      title="Callouts"
      eyebrow="Bulk Email"
      lede="Mission callouts ask who can fly. Open one to see each person's answer."
    >
      <Card>
        {callouts.isError ? (
          <p className="field__error" role="alert">
            The callouts could not be loaded.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={CALLOUT_COLUMNS}
            rows={rows}
            rowKey={(row) => row.id}
            caption={`${rows.length} ${rows.length === 1 ? 'callout' : 'callouts'}`}
            emptyTitle="No callout has been sent"
            emptyDescription="To send one, open Compose and switch on This is a mission callout."
            isLoading={callouts.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}

/** The table's columns: the subject, when it went, whether it is open, then the counts. */
export const CALLOUT_COLUMNS: Column<CalloutSummary>[] = [
  {
    key: 'subject',
    header: 'Subject',
    minWidth: '14rem',
    render: (row) => <Link to={`/bulk-email/callouts/${row.id}`}>{row.subject}</Link>,
    sortValue: (row) => row.subject,
  },
  {
    key: 'started_at',
    header: 'Sent',
    width: '6.5rem',
    render: (row) => <DateText value={row.started_at} />,
    sortValue: (row) => row.started_at,
  },
  {
    key: 'closes_at',
    header: 'Answers',
    width: '19rem',
    render: (row) => (
      <span className="callouts__state">
        <StatusDot tone={row.is_open ? 'current' : 'none'} label={openLabel(row)} />
        <span aria-hidden="true">{openLabel(row)}</span>
      </span>
    ),
    sortValue: (row) => (row.is_open ? 1 : 0),
  },
  {
    key: 'sender',
    header: 'From',
    width: '8rem',
    render: (row) => row.sender || '—',
    sortValue: (row) => row.sender,
  },
  {
    key: 'dart_name',
    header: 'DART',
    width: '7rem',
    render: (row) => row.dart_name || '—',
    sortValue: (row) => row.dart_name,
  },
  {
    key: 'available',
    header: 'Available',
    numeric: true,
    width: '5.5rem',
    render: (row) => row.counts.available,
    sortValue: (row) => row.counts.available,
  },
  {
    key: 'limited',
    header: 'With limits',
    numeric: true,
    width: '6rem',
    render: (row) => row.counts.limited,
    sortValue: (row) => row.counts.limited,
  },
  {
    key: 'unavailable',
    header: 'Not available',
    numeric: true,
    width: '7rem',
    render: (row) => row.counts.unavailable,
    sortValue: (row) => row.counts.unavailable,
  },
  {
    key: 'no_answer',
    header: 'No answer',
    numeric: true,
    width: '5.5rem',
    render: (row) => row.counts.no_answer,
    sortValue: (row) => row.counts.no_answer,
  },
];
