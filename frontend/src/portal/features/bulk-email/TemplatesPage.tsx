/**
 * `/bulk-email/templates`: the messages CalDART management keeps to start a draft
 * from, such as the monthly newsletter, shared by every manager.
 *
 * One table and one form: **New template** opens the form empty, and each row's
 * **Edit** opens it on that template, which is also how one is renamed. Each row's
 * trashcan asks before it deletes. A draft starts from a template on the compose
 * screen, with **Start from a template**.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { EmailTemplate, EmailTemplateWrite } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Page } from '@/portal/components/Page';
import './bulk-email.css';
import { useCreateTemplate, useDeleteTemplate, useTemplates, useUpdateTemplate } from './reuseApi';
import { TemplateForm } from './TemplateForm';

/** Which form is open: a new template, or the edit of one. */
type OpenForm = { mode: 'new' } | { mode: 'edit'; id: number } | null;

/** A line for the screen's status: what happened, and whether it went wrong. */
interface Notice {
  text: string;
  isError: boolean;
}

/** The templates table, its row controls, and the new-and-edit form. */
export function TemplatesPage(): JSX.Element {
  const [openForm, setOpenForm] = useState<OpenForm>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const templates = useTemplates();
  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const remove = useDeleteTemplate();
  const rows = templates.data ?? [];
  const editing =
    openForm?.mode === 'edit' ? rows.find((template) => template.id === openForm.id) : undefined;

  const handleClose = (): void => {
    create.reset();
    update.reset();
    setOpenForm(null);
  };

  const handleNew = (): void => {
    create.reset();
    setNotice(null);
    setOpenForm({ mode: 'new' });
  };

  const handleEdit = (template: EmailTemplate): void => {
    update.reset();
    setNotice(null);
    setOpenForm({ mode: 'edit', id: template.id });
  };

  const handleCreate = (input: EmailTemplateWrite): void => {
    create.mutate(input, {
      onSuccess: (saved) => {
        setNotice({ text: `${saved.name} saved.`, isError: false });
        handleClose();
      },
    });
  };

  const handleUpdate = (id: number, input: EmailTemplateWrite): void => {
    update.mutate(
      { id, patch: input },
      {
        onSuccess: (saved) => {
          setNotice({ text: `${saved.name} saved.`, isError: false });
          handleClose();
        },
      },
    );
  };

  const handleDelete = (template: EmailTemplate): Promise<void> =>
    remove.mutateAsync(template.id).then(
      () => {
        if (openForm?.mode === 'edit' && openForm.id === template.id) handleClose();
        setNotice({ text: `${template.name} deleted.`, isError: false });
      },
      (error: unknown) =>
        setNotice({
          text: error instanceof Error ? error.message : `${template.name} was not deleted.`,
          isError: true,
        }),
    );

  const columns: Column<EmailTemplate>[] = [
    {
      key: 'name',
      header: 'Name',
      minWidth: '14rem',
      render: (template) => template.name,
      sortValue: (template) => template.name.toLowerCase(),
    },
    {
      key: 'subject',
      header: 'Subject',
      minWidth: '14rem',
      render: (template) => template.subject || '—',
    },
    {
      key: 'email_type_name',
      header: 'Type',
      width: '7rem',
      render: (template) => template.email_type_name || '—',
      sortValue: (template) => template.email_type_name,
    },
    {
      key: 'updated_at',
      header: 'Last edited',
      width: '7rem',
      render: (template) => <DateText value={template.updated_at} />,
      sortValue: (template) => template.updated_at,
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '7rem',
      render: (template) => (
        <span className="cluster cluster--nowrap">
          <Button
            variant="quiet"
            small
            aria-label={`Edit ${template.name}`}
            onClick={() => handleEdit(template)}
          >
            Edit
          </Button>
          <DeleteButton
            label={`Delete ${template.name}`}
            disabled={remove.isPending}
            onDelete={() => handleDelete(template)}
          />
        </span>
      ),
    },
  ];

  return (
    <Page
      title="Templates"
      eyebrow="Bulk Email"
      lede="Messages you send again and again, such as the monthly newsletter. Start a draft from one on the compose screen; changing the draft leaves the template as it is."
      actions={openForm === null ? <Button onClick={handleNew}>New template</Button> : null}
    >
      {openForm?.mode === 'new' ? (
        <Card eyebrow="New" title="New template">
          <TemplateForm
            submitLabel="Save template"
            pending={create.isPending}
            error={create.error}
            onSubmit={handleCreate}
            onCancel={handleClose}
          />
        </Card>
      ) : null}

      {editing === undefined ? null : (
        <Card eyebrow="Edit" title={editing.name}>
          <TemplateForm
            key={editing.id}
            template={editing}
            submitLabel="Save template"
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
        {templates.isError ? (
          <p className="field__error" role="alert">
            The templates could not be loaded.
          </p>
        ) : (
          <DataTable
            singleLine
            columns={columns}
            rows={rows}
            rowKey={(template) => template.id}
            caption={`${rows.length} ${rows.length === 1 ? 'template' : 'templates'}`}
            emptyTitle="No templates yet"
            emptyDescription="Press New template, or save a draft's message with Save as a template."
            isLoading={templates.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}
