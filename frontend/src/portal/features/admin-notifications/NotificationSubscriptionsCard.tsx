/**
 * The *Who hears about what* card of `/admin/notifications`: every address
 * subscribed to notifications, one per line, with a button to edit its events,
 * pause or resume it, or delete it, and the form that subscribes another.
 *
 * One form is open at a time, under the table: **New subscription** opens it
 * empty and **Edit** opens it for that row, each closing the other.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { NotificationSubscription } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { StatusDot } from '@/portal/components/StatusChip';
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
  const [notice, setNotice] = useState<string | null>(null);

  const list = useNotificationSubscriptions();
  const catalog = useNotificationEvents();
  const update = useUpdateNotificationSubscription();
  const remove = useDeleteNotificationSubscription();
  const isBusy = update.isPending || remove.isPending;
  const events = catalog.data ?? [];

  const handleToggleActive = (row: NotificationSubscription): void => {
    const isActive = !row.is_active;
    update.mutate(
      { id: row.id, patch: { is_active: isActive } },
      {
        onSuccess: () => setNotice(isActive ? 'Resumed.' : 'Paused.'),
        onError: (error) => setNotice(errorText(error, 'The change was not saved.')),
      },
    );
  };

  const handleDelete = (row: NotificationSubscription): void => {
    remove.mutate(row.id, {
      onSuccess: () => setNotice('Deleted.'),
      onError: (error) => setNotice(errorText(error, 'The subscription was not deleted.')),
    });
  };

  const handleAdd = (): void => {
    setNotice(null);
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (row: NotificationSubscription): void => {
    setNotice(null);
    setOpenForm((open) =>
      open?.mode === 'edit' && open.id === row.id ? null : { mode: 'edit', id: row.id },
    );
  };

  const handleFormDone = (): void => {
    setOpenForm(null);
  };

  const columns: Column<NotificationSubscription>[] = [
    {
      key: 'recipient',
      header: 'Recipient',
      width: '14rem',
      render: (row) => recipientLabel(row),
      sortValue: (row) => recipientLabel(row),
    },
    {
      key: 'events',
      header: 'Events',
      // A plain-text cell: the single-line table cuts it with an ellipsis and
      // keeps the whole list in the cell's title.
      render: (row) => eventLabels(row.events, events),
    },
    {
      key: 'is_active',
      header: 'Active',
      width: '5rem',
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
      width: '12rem',
      render: (row) => (
        <span className="cluster cluster--nowrap">
          <Button variant="quiet" small disabled={isBusy} onClick={() => handleEdit(row)}>
            Edit
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
  const editing =
    openForm?.mode === 'edit' ? rows.find((subscription) => subscription.id === openForm.id) : null;

  return (
    <Card eyebrow="By email" title="Who hears about what">
      <p className="muted">
        Each subscription sends one address an email whenever one of its events happens.{' '}
        <strong>Edit</strong> changes its events; <strong>Pause</strong> stops the emails without
        forgetting the events.
      </p>

      {openForm?.mode === 'new' ? null : <Button onClick={handleAdd}>New subscription</Button>}

      {notice === null ? null : <p role="status">{notice}</p>}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${rows.length} subscription${rows.length === 1 ? '' : 's'}`}
        emptyTitle="Nobody is subscribed to a notification yet"
        isLoading={list.isLoading}
      />

      {openForm?.mode === 'new' ? <NotificationSubscriptionForm onDone={handleFormDone} /> : null}
      {editing === null || editing === undefined ? null : (
        <NotificationSubscriptionForm
          key={editing.id}
          subscription={editing}
          onDone={handleFormDone}
        />
      )}

      {list.isError ? (
        <p className="field__error" role="alert">
          {errorText(list.error, 'The subscriptions could not be loaded.')}
        </p>
      ) : null}
    </Card>
  );
}
