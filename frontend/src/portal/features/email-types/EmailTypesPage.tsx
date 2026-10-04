/**
 * `/bulk-email/types` — the types of bulk email, for a system administrator.
 *
 * One table, in a card, and one form: **Add an email type** opens the form empty and
 * each row's **Edit** opens it on that type, above the table.  The focus moves into the
 * form as it opens, scrolling it into view, and back to the button that opened it as it
 * closes, Escape included; a toast says what each save and delete did. Each row's trashcan asks before it
 * deletes. A type a bulk email has used cannot be deleted: its trashcan is grayed, and
 * holding the pointer over it says what to do instead. The description and the
 * senders wrap, so they read in full.
 */
import { useCallback, useRef, useState } from 'react';
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
import { useToast } from '@/portal/components/Toast';
import { usePanelFocus } from '@/portal/components/focus';
import { useCreateEmailType, useDeleteEmailType, useEmailTypes, useUpdateEmailType } from './api';
import { EmailTypeForm } from './EmailTypeForm';

/** Which form is open: a new type, or the edit of one. */
type OpenForm = { mode: 'new' } | { mode: 'edit'; id: number } | null;

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
  const toast = useToast();

  const types = useEmailTypes();
  const create = useCreateEmailType();
  const update = useUpdateEmailType();
  const remove = useDeleteEmailType();
  const rows = types.data ?? [];
  const editing =
    openForm?.mode === 'edit' ? rows.find((emailType) => emailType.id === openForm.id) : undefined;

  const resetCreate = create.reset;
  const resetUpdate = update.reset;
  const handleClose = useCallback((): void => {
    resetCreate();
    resetUpdate();
    setOpenForm(null);
  }, [resetCreate, resetUpdate]);
  const addRef = useRef<HTMLButtonElement>(null);
  const openKey =
    openForm === null ? null : openForm.mode === 'new' ? 'new' : `edit-${openForm.id}`;
  const formRef = usePanelFocus(openKey, handleClose, addRef);

  const handleAdd = (): void => {
    create.reset();
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (emailType: EmailType): void => {
    update.reset();
    setOpenForm({ mode: 'edit', id: emailType.id });
  };

  const handleCreate = (input: EmailTypeInput): void => {
    create.mutate(input, {
      onSuccess: (saved) => {
        toast.show(`${saved.name} added.`, 'success');
        handleClose();
      },
    });
  };

  const handleUpdate = (id: number, input: EmailTypeInput): void => {
    update.mutate(
      { id, input },
      {
        onSuccess: (saved) => {
          toast.show(`${saved.name} saved.`, 'success');
          handleClose();
        },
      },
    );
  };

  const handleDelete = (emailType: EmailType): Promise<void> =>
    remove.mutateAsync(emailType.id).then(
      () => {
        if (openForm?.mode === 'edit' && openForm.id === emailType.id) handleClose();
        toast.show(`${emailType.name} deleted.`, 'success');
      },
      (error: unknown) =>
        toast.show(
          error instanceof Error ? error.message : `${emailType.name} was not deleted.`,
          'error',
        ),
    );

  // The name tells the rows apart and stays pinned while a phone scrolls the table; the
  // description wraps and never narrows below a readable width, so it reads in full; the
  // actions come last, wide enough for an open delete confirmation beside Edit. Whether
  // it can be turned off, then who may send it, give way on a narrow screen.
  const columns: Column<EmailType>[] = [
    {
      key: 'name',
      header: 'Name',
      width: '10rem',
      isIdentity: true,
      render: (emailType) => emailType.name,
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '12rem',
      isActions: true,
      narrowWidth: '7rem',
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
      minWidth: '13rem',
      wrap: true,
      render: (emailType) => emailType.description,
    },
    {
      key: 'senders',
      header: 'Who may send it',
      width: '12rem',
      wrap: true,
      dropOrder: 2,
      render: (emailType) => sendersText(emailType),
    },
    {
      key: 'allow_opt_out',
      header: 'Can be turned off',
      width: '7rem',
      wrap: true,
      dropOrder: 1,
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
      actions={
        openForm === null ? (
          <Button ref={addRef} onClick={handleAdd}>
            Add an email type
          </Button>
        ) : null
      }
    >
      <div ref={formRef}>
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
      </div>

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
          emptyAction={
            openForm === null ? (
              <Button variant="secondary" onClick={handleAdd}>
                Add an email type
              </Button>
            ) : undefined
          }
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
