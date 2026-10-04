/**
 * The *Notification emails* card of `/admin/notifications`: every address
 * subscribed to notifications, one per line, with a button to edit its events,
 * pause or resume it, or delete it, and the form that subscribes another.
 *
 * One form is open at a time, always under the table: **Add an address** opens it
 * empty and **Edit** opens it for that row, each closing the other.  The focus moves
 * into the form as it opens, scrolling it into view, and back to the button that
 * opened it as it closes, Escape included.  What every action did is said in a toast.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX, MouseEvent } from 'react';

import type { NotificationSubscription } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { useFocusAfterSave, usePanelFocus } from '@/portal/components/focus';
import {
  useDeleteNotificationSubscription,
  useNotificationEvents,
  useNotificationSubscriptions,
  useUpdateNotificationSubscription,
} from './api';
import { eventLabels, recipientLabel } from './labels';
import { NotificationSubscriptionForm } from './NotificationSubscriptionForm';

/** Which form is open: a new subscription, or the edit of one. */
type OpenForm = { mode: 'new' } | { mode: 'edit'; id: number } | null;

/** An error's message for the status line, or `fallback` when it carries none. */
function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

/** The subscriptions table, its row controls, and the form behind Add an address and Edit. */
export function NotificationSubscriptionsCard(): JSX.Element {
  const [openForm, setOpenForm] = useState<OpenForm>(null);
  const toast = useToast();
  const newRef = useRef<HTMLButtonElement>(null);
  const handleFormDone = useCallback((): void => setOpenForm(null), []);
  const openKey =
    openForm === null ? null : openForm.mode === 'new' ? 'new' : `edit-${openForm.id}`;
  const formRef = usePanelFocus(openKey, handleFormDone, newRef);

  const list = useNotificationSubscriptions();
  const catalog = useNotificationEvents();
  const update = useUpdateNotificationSubscription();
  const remove = useDeleteNotificationSubscription();
  const isBusy = update.isPending || remove.isPending;
  // Every row's buttons wait while one acts; the one pressed gets the focus back.
  const pressedRef = useRef<HTMLElement | null>(null);
  useFocusAfterSave(pressedRef, isBusy);
  const handlePress = (event: MouseEvent<HTMLElement>): void => {
    pressedRef.current = event.currentTarget;
  };
  const events = catalog.data ?? [];

  const handleToggleActive = (row: NotificationSubscription): void => {
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

  const handleDelete = (row: NotificationSubscription): Promise<void> =>
    remove.mutateAsync(row.id).then(
      () => toast.show('Deleted.', 'success'),
      (error) =>
        toast.show(errorText(error, "The address wasn't deleted. Try again in a moment."), 'error'),
    );

  const handleAdd = (): void => {
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (row: NotificationSubscription): void => {
    setOpenForm((open) =>
      open?.mode === 'edit' && open.id === row.id ? null : { mode: 'edit', id: row.id },
    );
  };

  // The recipient tells the rows apart and starts at the left; the events never narrow
  // below a readable width and wrap to show every one; the actions come last, headed for a screen reader, with room
  // for Edit, Pause, and an open delete confirmation side by side.
  const columns: Column<NotificationSubscription>[] = [
    {
      key: 'recipient',
      header: 'Recipient',
      minWidth: '12rem',
      isIdentity: true,
      render: (row) => recipientLabel(row),
      sortValue: (row) => recipientLabel(row),
    },
    {
      key: 'events',
      header: 'Events',
      minWidth: '14rem',
      // The list is what the row is for, so it wraps in the cell to be read whole.
      wrap: true,
      render: (row) => eventLabels(row.events, events),
    },
    {
      key: 'is_active',
      header: 'Active',
      // The dot and its longer word, "Paused", with the cell's padding.
      width: '7rem',
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
      narrowWidth: '8rem',
      render: (row) => {
        const which = `notifications for ${recipientLabel(row)}`;
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
    <Card title="Notification emails">
      <p className="muted">
        Each address gets an email whenever one of its events happens. Pause stops the emails and
        keeps the settings.
      </p>

      {openForm?.mode === 'new' ? null : (
        <Button ref={newRef} onClick={handleAdd}>
          Add an address
        </Button>
      )}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${rows.length} address${rows.length === 1 ? '' : 'es'}`}
        emptyTitle="No address gets notifications yet"
        isLoading={list.isLoading}
      />

      {openForm === null ? null : (
        <div ref={formRef}>
          {openForm.mode === 'new' ? (
            <NotificationSubscriptionForm onDone={handleFormDone} />
          ) : editing === null || editing === undefined ? null : (
            <NotificationSubscriptionForm
              key={editing.id}
              subscription={editing}
              onDone={handleFormDone}
            />
          )}
        </div>
      )}

      {list.isError ? (
        <p className="field__error" role="alert">
          {errorText(list.error, "The addresses didn't load. Try again in a moment.")}
        </p>
      ) : null}
    </Card>
  );
}
