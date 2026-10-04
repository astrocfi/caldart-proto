/**
 * `/bulk-email/types` — the types of bulk email, for a system administrator.
 *
 * One table, in a card, and one form: **Add an email type** opens the form empty and
 * each row's **Edit** opens it on that type. Each row's trashcan asks before it
 * deletes. A type a bulk email has used cannot be deleted: its trashcan is grayed, and
 * holding the pointer over it says what to do instead. The description and the
 * senders wrap, so they read in full.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { EmailType, EmailTypeInput } from '@/portal/api/types';
import { roleLabel } from '@/portal/choices';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusChip';
import { useCreateEmailType, useDeleteEmailType, useEmailTypes, useUpdateEmailType } from './api';
import { EmailTypeForm } from './EmailTypeForm';

/** Which form is open: a new type, or the edit of one. */
type OpenForm = { mode: 'new' } | { mode: 'edit'; id: number } | null;

/** A line for the screen's status: what happened, and whether it went wrong. */
interface Notice {
  text: string;
  isError: boolean;
}

/** Why a type a bulk email has used cannot be deleted, and what to do instead. */
export function inUseReason(emailType: EmailType): string {
  return `${emailType.name} has been used for a bulk email, so it cannot be deleted. To keep DART leaders and CalDART management from sending it, take their roles off it instead.`;
}

/** The roles that send `emailType`, in words. */
export function sendersText(emailType: EmailType): string {
  if (emailType.sender_roles.length === 0) return 'System administrators only';
  return emailType.sender_roles.map(roleLabel).join(', ');
}

/** The email types table, its row controls, and the add-and-edit form. */
export function EmailTypesPage(): JSX.Element {
  const [openForm, setOpenForm] = useState<OpenForm>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const types = useEmailTypes();
  const create = useCreateEmailType();
  const update = useUpdateEmailType();
  const remove = useDeleteEmailType();
  const rows = types.data ?? [];
  const editing =
    openForm?.mode === 'edit' ? rows.find((emailType) => emailType.id === openForm.id) : undefined;

  const handleClose = (): void => {
    create.reset();
    update.reset();
    setOpenForm(null);
  };

  const handleAdd = (): void => {
    create.reset();
    setNotice(null);
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (emailType: EmailType): void => {
    update.reset();
    setNotice(null);
    setOpenForm({ mode: 'edit', id: emailType.id });
  };

  const handleCreate = (input: EmailTypeInput): void => {
    create.mutate(input, {
      onSuccess: (saved) => {
        setNotice({ text: `${saved.name} added.`, isError: false });
        handleClose();
      },
    });
  };

  const handleUpdate = (id: number, input: EmailTypeInput): void => {
    update.mutate(
      { id, input },
      {
        onSuccess: (saved) => {
          setNotice({ text: `${saved.name} saved.`, isError: false });
          handleClose();
        },
      },
    );
  };

  const handleDelete = (emailType: EmailType): Promise<void> =>
    remove.mutateAsync(emailType.id).then(
      () => {
        if (openForm?.mode === 'edit' && openForm.id === emailType.id) handleClose();
        setNotice({ text: `${emailType.name} deleted.`, isError: false });
      },
      (error: unknown) =>
        setNotice({
          text: error instanceof Error ? error.message : `${emailType.name} was not deleted.`,
          isError: true,
        }),
    );

  // The name and the actions come first, narrow enough to stay in sight on a phone; the
  // description takes whatever room the fixed widths leave.
  const columns: Column<EmailType>[] = [
    {
      key: 'name',
      header: 'Name',
      width: '10rem',
      wrap: true,
      render: (emailType) => emailType.name,
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '7rem',
      keepInSight: true,
      render: (emailType) => (
        <span className="cluster cluster--nowrap">
          <Button
            variant="quiet"
            small
            aria-label={`Edit ${emailType.name}`}
            onClick={() => handleEdit(emailType)}
          >
            Edit
          </Button>
          <DeleteButton
            label={`Delete ${emailType.name}`}
            disabled={remove.isPending || emailType.in_use}
            title={emailType.in_use ? inUseReason(emailType) : undefined}
            onDelete={() => handleDelete(emailType)}
          />
        </span>
      ),
    },
    {
      key: 'description',
      header: 'What it is for',
      wrap: true,
      render: (emailType) => emailType.description,
    },
    {
      key: 'senders',
      header: 'Who may send it',
      width: '16rem',
      wrap: true,
      render: (emailType) => sendersText(emailType),
    },
    {
      key: 'allow_opt_out',
      header: 'Can be turned off',
      width: '9rem',
      wrap: true,
      // The word says it; the dot, hidden from a screen reader, only colors it.
      render: (emailType) => (
        <>
          <span aria-hidden="true">
            <StatusDot
              tone={emailType.allow_opt_out ? 'current' : 'none'}
              label={emailType.allow_opt_out ? 'Yes' : 'No'}
            />
          </span>{' '}
          {emailType.allow_opt_out ? 'Yes' : 'No'}
        </>
      ),
    },
  ];

  return (
    <Page
      title="Email types"
      eyebrow="Bulk Email"
      lede="The types of bulk email CalDART sends. Each one says who may send it and whether members may turn it off on their Email preferences."
      actions={openForm === null ? <Button onClick={handleAdd}>Add an email type</Button> : null}
    >
      {openForm?.mode === 'new' ? (
        <Card eyebrow="New" title="Add an email type">
          <EmailTypeForm
            submitLabel="Add type"
            pending={create.isPending}
            error={create.error}
            onSubmit={handleCreate}
            onCancel={handleClose}
          />
        </Card>
      ) : null}

      {editing === undefined ? null : (
        <Card eyebrow="Edit" title={editing.name}>
          <EmailTypeForm
            key={editing.id}
            emailType={editing}
            submitLabel="Save type"
            pending={update.isPending}
            error={update.error}
            onSubmit={(input) => handleUpdate(editing.id, input)}
            onCancel={handleClose}
          />
        </Card>
      )}

      {notice === null ? null : (
        <p
          role={notice.isError ? 'alert' : 'status'}
          className={notice.isError ? 'field__error' : ''}
        >
          {notice.text}
        </p>
      )}

      <Card>
        <DataTable
          singleLine
          columns={columns}
          rows={rows}
          rowKey={(emailType) => emailType.id}
          caption="Email types"
          isLoading={types.isPending}
          emptyTitle="No email types yet"
          emptyDescription="Add one, and CalDART management can choose it when they send a bulk email."
        />
        {types.isError ? (
          <p className="field__error" role="alert">
            The email types could not be loaded.
          </p>
        ) : null}
        {types.isSuccess && rows.some((emailType) => emailType.in_use) ? (
          <p className="muted">
            A grayed trashcan marks a type a bulk email has used, which cannot be deleted. Take the
            senders off it instead to stop it being sent.
          </p>
        ) : null}
      </Card>
    </Page>
  );
}
