/**
 * The *Who hears about what* card of `/admin/notifications`: every address
 * subscribed to notifications, one per line, with a button to edit its events,
 * pause or resume it, or delete it, and the form that subscribes another.
 *
 * One form is open at a time, always under the table: **New subscription** opens it
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

/** The subscriptions table, its row controls, and the form behind New subscription and Edit. */
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
        onError: (error) => toast.show(errorText(error, 'The change was not saved.'), 'error'),
      },
    );
  };

  const handleDelete = (row: NotificationSubscription): Promise<void> =>
    remove.mutateAsync(row.id).then(
      () => toast.show('Deleted.', 'success'),
      (error) => toast.show(errorText(error, 'The subscription was not deleted.'), 'error'),
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
  // below a readable width; the actions come last, headed for a screen reader, with room
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
      // A plain-text cell: the single-line table cuts it with an ellipsis and
      // keeps the whole list in the cell's title.
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
      render: (row) => (
        <span className="cluster cluster--nowrap">
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleEdit(row)}>
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
          >
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
    <Card title="Who hears about what">
      <p className="muted">
        Each subscription sends one address an email whenever one of its events happens.{' '}
        <strong>Edit</strong> changes its events; <strong>Pause</strong> stops the emails without
        forgetting the events.
      </p>

      {openForm?.mode === 'new' ? null : (
        <Button ref={newRef} onClick={handleAdd}>
          New subscription
        </Button>
      )}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${rows.length} subscription${rows.length === 1 ? '' : 's'}`}
        emptyTitle="Nobody is subscribed to a notification yet"
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
          {errorText(list.error, 'The subscriptions could not be loaded.')}
        </p>
      ) : null}
    </Card>
  );
}
