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
import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useBulkSender } from '@/portal/features/bulk-email/api';
import { DROP_ORDER } from '@/portal/features/bulk-email/dropOrder';
import { SenderNotice } from '@/portal/features/bulk-email/SenderNotice';
import { useCallouts } from './api';
import './callouts.css';
import { openLabel } from './labels';

/** Every callout, one line each. */
export function CalloutsPage(): JSX.Element {
  const callouts = useCallouts();
  const sender = useBulkSender();
  const rows = callouts.data ?? [];
  // A DART leader with no DART cannot write a callout, so the empty list offers no way to.
  const canSend = sender.data?.can_send !== false;

  return (
    <Page
      title="Callouts"
      lede="Mission callouts ask who can fly. Open one to see each person's answer."
    >
      {sender.data === undefined ? null : <SenderNotice sender={sender.data} />}
      <Card>
        {callouts.isError ? (
          <p className="field__error" role="alert">
            The callouts didn&apos;t load. Try again in a moment.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={CALLOUT_COLUMNS}
            rows={rows}
            rowKey={(row) => row.id}
            initialSort={{ key: 'started_at', direction: 'desc' }}
            caption={`${rows.length} ${rows.length === 1 ? 'callout' : 'callouts'}`}
            emptyTitle="No callout has been sent"
            // A leader with no DART reads why in the notice above, so the empty list
            // does not say it a second time.
            emptyDescription={
              canSend
                ? 'To send one, write an email and switch on This is a mission callout.'
                : undefined
            }
            emptyAction={
              canSend ? <ButtonLink to="/bulk-email/compose">New email</ButtonLink> : undefined
            }
            isLoading={callouts.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}

/**
 * The table's columns: the subject, when it went, whether it is open (wrapping, so the
 * closing time reads in full), then the counts. Who sent it and their DART give way
 * first when the table would not fit its card.
 */
export const CALLOUT_COLUMNS: Column<CalloutSummary>[] = [
  {
    key: 'subject',
    header: 'Subject',
    minWidth: '12rem',
    isIdentity: true,
    render: (row) => <Link to={`/bulk-email/callouts/${row.id}`}>{row.subject}</Link>,
    sortValue: (row) => row.subject,
  },
  {
    key: 'started_at',
    header: 'Sent',
    width: '6.5rem',
    noWrap: true,
    render: (row) => <DateText value={row.started_at} />,
    sortValue: (row) => row.started_at,
  },
  {
    key: 'closes_at',
    header: 'Answers',
    width: '13rem',
    wrap: true,
    render: (row) => (
      <span className="callouts__state">
        <StatusDot tone={row.is_open ? 'current' : 'none'} label={openLabel(row)} />
      </span>
    ),
    sortValue: (row) => (row.is_open ? 1 : 0),
  },
  {
    key: 'sender',
    header: 'From',
    width: '8rem',
    dropOrder: DROP_ORDER.from,
    render: (row) => row.sender || '—',
    sortValue: (row) => row.sender,
  },
  {
    key: 'dart_name',
    header: 'DART',
    width: '7rem',
    dropOrder: DROP_ORDER.dart,
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
