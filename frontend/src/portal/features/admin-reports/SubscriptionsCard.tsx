/**
 * The Subscriptions card of `/admin/reports`: every report CalDART emails on a
 * schedule, with a button to edit one, send it now, pause or resume it, or
 * delete it, and the form that sets up another.
 *
 * One form is open at a time: **New subscription** opens it above the table
 * and **Edit** opens it under the table for that row, each closing the other.
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

/** Which subscription form is open: a new one, or the edit of one subscription. */
type OpenForm = { mode: 'new' } | { mode: 'edit'; id: number } | null;

/** An error's message for the status line, or `fallback` when it carries none. */
function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** The subscriptions table, its row actions, and the form behind New subscription and Edit. */
export function SubscriptionsCard(): JSX.Element {
  const [openForm, setOpenForm] = useState<OpenForm>(null);
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

  const handleDelete = (row: ReportSubscription): Promise<void> =>
    remove.mutateAsync(row.id).then(
      () => setNotice('Deleted.'),
      (error) => setNotice(errorText(error, 'The subscription was not deleted.')),
    );

  const handleAdd = (): void => {
    setNotice(null);
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (row: ReportSubscription): void => {
    setNotice(null);
    setOpenForm((open) =>
      open?.mode === 'edit' && open.id === row.id ? null : { mode: 'edit', id: row.id },
    );
  };

  const handleFormDone = (): void => {
    setOpenForm(null);
  };

  // The report tells the rows apart and the actions come last, headed for a screen
  // reader, with room for every button. The last send, the next send, the formats, the
  // schedule, then the recipient give way on a narrow screen, so a laptop keeps the
  // recipient, the schedule, and the formats.
  const columns: Column<ReportSubscription>[] = [
    {
      key: 'report',
      header: 'Report',
      minWidth: '9.5rem',
      isIdentity: true,
      render: (row) => row.report_title,
      sortValue: (row) => row.report_title,
    },
    {
      key: 'recipient',
      header: 'Recipient',
      minWidth: '10rem',
      dropOrder: 5,
      render: (row) => recipientLabel(row),
      sortValue: (row) => recipientLabel(row),
    },
    {
      key: 'schedule',
      header: 'Schedule',
      minWidth: '8rem',
      dropOrder: 4,
      render: (row) => scheduleLabel(row.cadence, row.weekday),
    },
    {
      key: 'formats',
      header: 'Formats',
      width: '5.5rem',
      dropOrder: 3,
      render: (row) => FORMAT_LABELS[row.formats],
    },
    {
      key: 'last_sent_at',
      header: 'Last sent',
      width: '7rem',
      noWrap: true,
      dropOrder: 1,
      render: (row) => <DateText value={row.last_sent_at} />,
      sortValue: (row) => row.last_sent_at,
    },
    {
      key: 'next_due_on',
      header: 'Next',
      width: '7rem',
      noWrap: true,
      dropOrder: 2,
      render: (row) => <DateText value={row.next_due_on} />,
      sortValue: (row) => row.next_due_on,
    },
    {
      key: 'is_active',
      header: 'Active',
      width: '5rem',
      keepInSight: true,
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
      width: '16rem',
      isActions: true,
      narrowWidth: '9rem',
      render: (row) => (
        <span className="cluster cluster--nowrap">
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleEdit(row)}>
            Edit
          </Button>
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleSend(row)}>
            Send now
          </Button>
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleToggleActive(row)}>
            {row.is_active ? 'Pause' : 'Resume'}
          </Button>
          <DeleteButton
            label="Delete subscription"
            disabled={isBusy}
            onDelete={() => handleDelete(row)}
          />
        </span>
      ),
    },
  ];

  const rows = list.data ?? [];
  const editing =
    openForm?.mode === 'edit' ? rows.find((subscription) => subscription.id === openForm.id) : null;

  return (
    <Card eyebrow="By email" title="Subscriptions">
      <p className="muted">
        Each subscription emails one report, filtered and with the columns chosen for it, to one
        address on its schedule. <strong>Edit</strong> changes its filters, columns, formats, and
        schedule; <strong>Send now</strong> sends it at once without moving its next date.
      </p>

      {openForm?.mode === 'new' ? (
        <SubscriptionForm onDone={handleFormDone} />
      ) : (
        <Button onClick={handleAdd}>New subscription</Button>
      )}

      {notice === null ? null : <p role="status">{notice}</p>}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${rows.length} subscription${rows.length === 1 ? '' : 's'}`}
        emptyTitle="No reports are sent by email yet"
        isLoading={list.isLoading}
      />

      {editing === null || editing === undefined ? null : (
        <SubscriptionForm key={editing.id} subscription={editing} onDone={handleFormDone} />
      )}

      {list.isError ? (
        <p className="field__error" role="alert">
          {errorText(list.error, 'The subscriptions could not be loaded.')}
        </p>
      ) : null}
    </Card>
  );
}
