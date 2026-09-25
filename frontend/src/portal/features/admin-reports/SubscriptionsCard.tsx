/**
 * The Subscriptions card of `/admin/reports`: every report CalDART emails on a
 * schedule, with a button to send one now, pause or resume it, or delete it,
 * and the form that sets up another.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { ReportRunResult, ReportSubscription } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { StatusDot } from '@/portal/components/StatusChip';
import {
  useDeleteSubscription,
  useSendSubscription,
  useSubscriptions,
  useUpdateSubscription,
} from '@/portal/reports/api';
import { FORMAT_LABELS, recipientLabel, scheduleLabel } from './labels';
import { SubscriptionForm } from './SubscriptionForm';

/**
 * The line a **Send now** leaves: who the report reached, or why it did not.
 *
 * @param result the one-send run the server answered with.
 * @param recipient the recipient's name, or their address outside CalDART.
 * @returns `Sent to <recipient>.`, or the reason nothing went.
 */
export function sendNotice(result: ReportRunResult, recipient: string): string {
  if (result.sent > 0) return `Sent to ${recipient}.`;
  if ((result.skipped_by_reason.not_permitted ?? 0) > 0) {
    return (
      `Not sent: ${recipient} no longer holds a role that may read this report, ` +
      'so the subscription is paused.'
    );
  }
  return `Not sent to ${recipient}: the report could not be built or the mail server refused it.`;
}

/** An error's message for the status line, or `fallback` when it carries none. */
function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** The subscriptions table, its row actions, and the form behind New subscription. */
export function SubscriptionsCard(): JSX.Element {
  const [isAdding, setIsAdding] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const list = useSubscriptions();
  const send = useSendSubscription();
  const update = useUpdateSubscription();
  const remove = useDeleteSubscription();
  const isBusy = send.isPending || update.isPending || remove.isPending;

  const handleSend = (row: ReportSubscription): void => {
    const recipient = recipientLabel(row);
    send.mutate(row.id, {
      onSuccess: (result) => setNotice(sendNotice(result, recipient)),
      onError: (error) => setNotice(errorText(error, `Not sent to ${recipient}.`)),
    });
  };

  const handleToggleActive = (row: ReportSubscription): void => {
    const isActive = !row.is_active;
    update.mutate(
      { id: row.id, patch: { is_active: isActive } },
      {
        onSuccess: () => setNotice(isActive ? 'Resumed.' : 'Paused.'),
        onError: (error) => setNotice(errorText(error, 'The change was not saved.')),
      },
    );
  };

  const handleDelete = (row: ReportSubscription): void => {
    remove.mutate(row.id, {
      onSuccess: () => setNotice('Deleted.'),
      onError: (error) => setNotice(errorText(error, 'The subscription was not deleted.')),
    });
  };

  const handleAdd = (): void => {
    setNotice(null);
    setIsAdding(true);
  };

  const handleFormDone = (): void => {
    setIsAdding(false);
  };

  const columns: Column<ReportSubscription>[] = [
    {
      key: 'report',
      header: 'Report',
      render: (row) => row.report_title,
      sortValue: (row) => row.report_title,
    },
    {
      key: 'recipient',
      header: 'Recipient',
      render: (row) => recipientLabel(row),
      sortValue: (row) => recipientLabel(row),
    },
    {
      key: 'schedule',
      header: 'Schedule',
      render: (row) => scheduleLabel(row.cadence, row.weekday),
    },
    { key: 'formats', header: 'Formats', render: (row) => FORMAT_LABELS[row.formats] },
    {
      key: 'last_sent_at',
      header: 'Last sent',
      render: (row) => <DateText value={row.last_sent_at} />,
      sortValue: (row) => row.last_sent_at,
    },
    {
      key: 'next_due_on',
      header: 'Next',
      render: (row) => <DateText value={row.next_due_on} />,
      sortValue: (row) => row.next_due_on,
    },
    {
      key: 'is_active',
      header: 'Active',
      render: (row) =>
        row.is_active ? (
          <StatusDot tone="current" label="Active" />
        ) : (
          <StatusDot tone="none" label="Paused" />
        ),
    },
    {
      key: 'actions',
      header: '',
      render: (row) => (
        <span className="cluster">
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleSend(row)}>
            Send now
          </Button>
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleToggleActive(row)}>
            {row.is_active ? 'Pause' : 'Resume'}
          </Button>
          <DeleteButton
            label="Delete subscription"
            disabled={isBusy}
            onClick={() => handleDelete(row)}
          />
        </span>
      ),
    },
  ];

  const rows = list.data ?? [];

  return (
    <Card eyebrow="By email" title="Subscriptions">
      <p className="muted">
        Each subscription emails one report, filtered and with the columns chosen when it was set
        up, to one address on its schedule. <strong>Send now</strong> sends it at once without
        moving its next date.
      </p>

      {isAdding ? (
        <SubscriptionForm onDone={handleFormDone} />
      ) : (
        <Button onClick={handleAdd}>New subscription</Button>
      )}

      {notice === null ? null : <p role="status">{notice}</p>}

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${rows.length} subscription${rows.length === 1 ? '' : 's'}`}
        emptyTitle="No reports are sent by email yet"
        isLoading={list.isLoading}
      />

      {list.isError ? (
        <p className="field__error" role="alert">
          {errorText(list.error, 'The subscriptions could not be loaded.')}
        </p>
      ) : null}
    </Card>
  );
}
