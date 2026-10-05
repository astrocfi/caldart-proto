/**
 * The Emailed reports card of `/admin/reports`: every report CalDART emails on a
 * schedule, with a button to edit one, send it now, pause or resume it, or
 * delete it, and the form that sets up another.
 *
 * One form is open at a time, always in the same place above the table:
 * **Email a report** opens it for a new one and a row's **Edit** for that row, each
 * closing the other.  The focus moves into the form as it opens and back to the button
 * that opened it as it closes, Escape included.  What every action did is said in a
 * toast, the portal's one way of confirming a save or a send.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX, MouseEvent } from 'react';

import type { ReportRunResult, ReportSubscription } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { useFocusAfterSave, usePanelFocus } from '@/portal/components/focus';
import {
  useDeleteSubscription,
  useSendSubscription,
  useSubscriptions,
  useUpdateSubscription,
} from '@/portal/reports/api';
import { FORMAT_LABELS, recipientLabel, reportName, scheduleLabel } from './labels';
import { SubscriptionForm } from './SubscriptionForm';
import './admin-reports.css';

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
      'so its emails are paused.'
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

/** The subscriptions table, its row actions, and the form behind Email a report and Edit. */
export function SubscriptionsCard(): JSX.Element {
  const [openForm, setOpenForm] = useState<OpenForm>(null);
  const toast = useToast();
  const newRef = useRef<HTMLButtonElement>(null);
  const handleFormDone = useCallback((): void => setOpenForm(null), []);
  const openKey =
    openForm === null ? null : openForm.mode === 'new' ? 'new' : `edit-${openForm.id}`;
  const formRef = usePanelFocus(openKey, handleFormDone, newRef);

  const list = useSubscriptions();
  const send = useSendSubscription();
  const update = useUpdateSubscription();
  const remove = useDeleteSubscription();
  const isBusy = send.isPending || update.isPending || remove.isPending;
  // Every row's buttons wait while one acts; the one pressed gets the focus back.
  const pressedRef = useRef<HTMLElement | null>(null);
  useFocusAfterSave(pressedRef, isBusy);
  const handlePress = (event: MouseEvent<HTMLElement>): void => {
    pressedRef.current = event.currentTarget;
  };

  const handleSend = (row: ReportSubscription): void => {
    const recipient = recipientLabel(row);
    send.mutate(row.id, {
      onSuccess: (result) =>
        toast.show(sendNotice(result, recipient), result.sent > 0 ? 'success' : 'error'),
      onError: (error) => toast.show(errorText(error, `Not sent to ${recipient}.`), 'error'),
    });
  };

  const handleToggleActive = (row: ReportSubscription): void => {
    const isActive = !row.is_active;
    update.mutate(
      { id: row.id, patch: { is_active: isActive } },
      {
        onSuccess: () => toast.show(isActive ? 'Resumed.' : 'Paused.', 'success'),
        onError: (error) =>
          toast.show(errorText(error, "The change wasn't saved. Try again in a moment."), 'error'),
      },
    );
  };

  const handleDelete = (row: ReportSubscription): Promise<void> =>
    remove.mutateAsync(row.id).then(
      () => toast.show('Deleted.', 'success'),
      (error) =>
        toast.show(
          errorText(error, "The emailed report wasn't deleted. Try again in a moment."),
          'error',
        ),
    );

  const handleAdd = (): void => {
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (row: ReportSubscription): void => {
    setOpenForm((open) =>
      open?.mode === 'edit' && open.id === row.id ? null : { mode: 'edit', id: row.id },
    );
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
      render: (row) => reportName(row.report, row.report_title),
      sortValue: (row) => reportName(row.report, row.report_title),
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
      render: (row) => {
        const which = `${reportName(row.report, row.report_title)} for ${recipientLabel(row)}`;
        return (
          <span className="cluster cluster--nowrap">
            <Button
              variant="quiet"
              small
              disabled={isBusy}
              aria-label={`Edit ${which}`}
              onClick={() => handleEdit(row)}
            >
              Edit
            </Button>
            <Button
              variant="quiet"
              small
              disabled={isBusy}
              onClick={(event) => {
                handlePress(event);
                handleSend(row);
              }}
              aria-label={`Send now: ${which}`}
            >
              Send now
            </Button>
            <Button
              variant="quiet"
              small
              disabled={isBusy}
              onClick={(event) => {
                handlePress(event);
                handleToggleActive(row);
              }}
              aria-label={`${row.is_active ? 'Pause' : 'Resume'} ${which}`}
            >
              {row.is_active ? 'Pause' : 'Resume'}
            </Button>
            <DeleteButton
              label={`Delete ${which}`}
              disabled={isBusy}
              onDelete={() => handleDelete(row)}
            />
          </span>
        );
      },
    },
  ];

  const rows = list.data ?? [];
  const editing =
    openForm?.mode === 'edit' ? rows.find((subscription) => subscription.id === openForm.id) : null;

  return (
    <Card title="Reports on a schedule">
      <p className="muted">
        CalDART emails each report to one address on the schedule you choose, with the filters and
        columns chosen for it.
      </p>

      {openForm?.mode === 'new' ? null : (
        <Button ref={newRef} onClick={handleAdd}>
          Email a report
        </Button>
      )}

      {openForm === null ? null : (
        <div ref={formRef} className="subscriptions__form">
          {openForm.mode === 'new' ? (
            <SubscriptionForm onDone={handleFormDone} />
          ) : editing === null || editing === undefined ? null : (
            <SubscriptionForm key={editing.id} subscription={editing} onDone={handleFormDone} />
          )}
        </div>
      )}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${rows.length} emailed report${rows.length === 1 ? '' : 's'}`}
        emptyTitle="No reports are sent by email yet"
        isLoading={list.isLoading}
      />

      {list.isError ? (
        <p className="field__error" role="alert">
          {errorText(list.error, "The emailed reports didn't load. Try again in a moment.")}
        </p>
      ) : null}
    </Card>
  );
}
