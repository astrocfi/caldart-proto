/**
 * `/admin/darts` — the teams members can join.
 *
 * One table, one button to add a DART, and the same form to edit one.  The
 * table offers only Edit; deleting a team happens in the form, where its name
 * and its people are on screen.  Any DART can be deleted: the members on it
 * become unaffiliated and a linked website page keeps its content, so the
 * confirmation says what will be left behind.  A team that has stopped flying
 * but should keep its history is made inactive instead.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { AdminDart, AdminDartPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import { useToast } from '@/portal/components/Toast';
import { DartForm, dartToValues, emptyDartValues } from './DartForm';
import { useAdminDarts, useCreateDart, useDeleteDart, useUpdateDart } from './api';

/** The first message of a DRF error value, or null when it holds none. */
function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
  return null;
}

/**
 * Field-keyed messages from a DRF 400, flattened to one line each.
 *
 * A nested contact's errors arrive keyed by position -- `contacts: {"0":
 * {"phone": [...]}}` -- and come out as `contacts.0.phone`, which is the key
 * the form's rows look themselves up by.
 */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.body || typeof error.body !== 'object') return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(error.body as Record<string, unknown>)) {
    const message = firstMessage(value);
    if (message !== null) {
      out[key] = message;
      continue;
    }
    if (key === 'contacts' && value && typeof value === 'object') {
      for (const [position, nested] of Object.entries(value as Record<string, unknown>)) {
        if (!nested || typeof nested !== 'object') continue;
        for (const [field, problem] of Object.entries(nested as Record<string, unknown>)) {
          const line = firstMessage(problem);
          if (line !== null) out[`contacts.${position}.${field}`] = line;
        }
      }
    }
  }
  return out;
}

/**
 * What deleting this DART leaves behind, as one sentence, or null when nothing.
 *
 * Both relations are `SET_NULL`: the members on the DART become unaffiliated
 * and a linked website page keeps its own content and loses its DART.  A DART
 * nothing points at needs no warning, so the sentence is only built when a
 * count is above zero, and it names only the counts that are.
 */
export function deleteWarning(dart: AdminDart): string | null {
  const clauses: string[] = [];
  if (dart.member_count > 0) {
    const members = `${dart.member_count} member${dart.member_count === 1 ? '' : 's'}`;
    clauses.push(`makes its ${members} unaffiliated`);
  }
  if (dart.page_count > 0) {
    const pages = `${dart.page_count} website page${dart.page_count === 1 ? '' : 's'}`;
    clauses.push(`unlinks ${pages}`);
  }
  if (clauses.length === 0) return null;
  return `Deleting ${dart.name} ${clauses.join(' and ')}. This cannot be undone.`;
}

/** The DART list, with the add-and-edit form and the delete guard. */
export function DartsPage(): JSX.Element {
  const darts = useAdminDarts();
  const create = useCreateDart();
  const update = useUpdateDart();
  const remove = useDeleteDart();
  const toast = useToast();

  // `'new'` is the add form; a number is the DART open for editing.
  const [editing, setEditing] = useState<number | 'new' | null>(null);

  const rows = darts.data ?? [];
  const open = typeof editing === 'number' ? rows.find((dart) => dart.id === editing) : undefined;

  const handleClose = (): void => {
    create.reset();
    update.reset();
    setEditing(null);
  };

  const handleCreate = (payload: AdminDartPatch): void => {
    create.mutate(payload, {
      onSuccess: (dart) => {
        toast.show(`${dart.name} added.`, 'success');
        handleClose();
      },
    });
  };

  const handleUpdate = (id: number, payload: AdminDartPatch): void => {
    update.mutate(
      { id, payload },
      {
        onSuccess: (dart) => {
          toast.show(`${dart.name} saved.`, 'success');
          handleClose();
        },
      },
    );
  };

  // The form waits on this promise to leave its confirmation, so a failure is
  // reported here rather than thrown on: the administrator stays in the
  // confirmation and reads what the server said, or the fallback wording when it
  // said nothing usable.
  const handleDelete = async (dart: AdminDart): Promise<void> => {
    try {
      await remove.mutateAsync(dart.id);
      toast.show(`${dart.name} deleted.`, 'success');
      setEditing(null);
    } catch (error) {
      toast.show(error instanceof ApiError ? error.message : 'That DART was not deleted.', 'error');
    }
  };

  const columns: Column<AdminDart>[] = [
    { key: 'name', header: 'Name', render: (dart) => dart.name, sortValue: (dart) => dart.name },
    {
      key: 'airport',
      header: 'Airport',
      width: '7rem',
      render: (dart) =>
        dart.airport_identifiers ? (
          <span className="mono">{dart.airport_identifiers}</span>
        ) : (
          <span className="muted">—</span>
        ),
      sortValue: (dart) => dart.airport_identifiers,
    },
    {
      key: 'website',
      header: 'Website',
      width: '9rem',
      sortable: false,
      render: (dart) =>
        dart.website_url ? (
          <a href={dart.website_url} target="_blank" rel="noreferrer">
            Visit
          </a>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: 'contacts',
      header: 'People',
      numeric: true,
      width: '6rem',
      render: (dart) => dart.contacts.length,
      sortValue: (dart) => dart.contacts.length,
    },
    {
      key: 'members',
      header: 'Members',
      numeric: true,
      width: '6rem',
      render: (dart) =>
        dart.member_count > 0 ? (
          <Link to={`/admin/members?dart=${dart.id}`}>{dart.member_count}</Link>
        ) : (
          dart.member_count
        ),
      sortValue: (dart) => dart.member_count,
    },
    {
      key: 'is_active',
      header: 'Status',
      width: '7rem',
      render: (dart) =>
        dart.is_active ? (
          <StatusChip tone="current" label="Active" />
        ) : (
          <StatusChip tone="none" label="Inactive" />
        ),
      sortValue: (dart) => (dart.is_active ? 0 : 1),
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '6rem',
      sortable: false,
      render: (dart) => (
        <Button variant="quiet" small onClick={() => setEditing(dart.id)}>
          Edit
        </Button>
      ),
    },
  ];

  return (
    <Page
      title="DARTs"
      eyebrow="Administration"
      lede="The teams a member can join. Everything here shows up in the list on the join form and on a member's profile."
      actions={
        editing === null ? (
          <Button
            onClick={() => {
              create.reset();
              setEditing('new');
            }}
          >
            Add a DART
          </Button>
        ) : null
      }
    >
      {editing === 'new' ? (
        <Card eyebrow="New" title="Add a DART">
          <DartForm
            initial={emptyDartValues()}
            submitLabel="Add DART"
            pending={create.isPending}
            errors={fieldErrors(create.error)}
            onSubmit={handleCreate}
            onCancel={handleClose}
          />
        </Card>
      ) : null}

      {open ? (
        <Card eyebrow="Edit" title={open.name}>
          <DartForm
            key={open.id}
            initial={dartToValues(open)}
            submitLabel="Save DART"
            pending={update.isPending}
            errors={fieldErrors(update.error)}
            onSubmit={(payload) => handleUpdate(open.id, payload)}
            onCancel={handleClose}
            onDelete={() => handleDelete(open)}
            deleteWarning={deleteWarning(open)}
            deletePending={remove.isPending}
          />
        </Card>
      ) : null}

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(dart) => dart.id}
        caption="DARTs"
        isLoading={darts.isPending}
        emptyTitle="No DARTs yet"
        emptyDescription="Add the first one, and it appears on the join form straight away."
        initialSort={{ key: 'name', direction: 'asc' }}
      />
    </Page>
  );
}
