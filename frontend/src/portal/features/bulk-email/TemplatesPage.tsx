/**
 * `/bulk-email/templates`: the messages CalDART management keeps to start a draft
 * from, such as the monthly newsletter, shared by every manager.
 *
 * One table and one form: **New template** opens the form empty, and each template's
 * name is a link that opens the form on it (`?edit=<id>`), which is also how one is
 * renamed. The trashcan sits right after the name and asks before it deletes. The
 * focus moves into the form as it opens, Escape closes it, and closing it puts the
 * focus back where it was. A draft starts from a template on the compose screen, with
 * **Start from a template**.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import type { EmailTemplate, EmailTemplateWrite } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { Page } from '@/portal/components/Page';
import { usePanelFocus } from '@/portal/components/focus';
import { DROP_ORDER } from './dropOrder';
import { FieldText } from './FieldChips';
import './bulk-email.css';
import { useCreateTemplate, useDeleteTemplate, useTemplates, useUpdateTemplate } from './reuseApi';
import { TemplateForm } from './TemplateForm';

/** Which form is open: a new template, or the edit of one. */
type OpenForm = { mode: 'new' } | { mode: 'edit'; id: number } | null;

/** The address's `?new` or `?edit=<id>`, as the form it opens. */
function openFormOf(params: URLSearchParams): OpenForm {
  const edit = Number(params.get('edit'));
  if (params.has('edit') && Number.isInteger(edit) && edit > 0) return { mode: 'edit', id: edit };
  return params.has('new') ? { mode: 'new' } : null;
}

/** A line for the screen's status: what happened, and whether it went wrong. */
interface Notice {
  text: string;
  isError: boolean;
}

/** The templates table, its row controls, and the new-and-edit form. */
export function TemplatesPage(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const openForm = openFormOf(params);
  const [notice, setNotice] = useState<Notice | null>(null);
  const newRef = useRef<HTMLButtonElement>(null);

  const templates = useTemplates();
  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const remove = useDeleteTemplate();
  const rows = templates.data ?? [];
  const editing =
    openForm?.mode === 'edit' ? rows.find((template) => template.id === openForm.id) : undefined;

  const { reset: resetCreate } = create;
  const { reset: resetUpdate } = update;
  const handleClose = useCallback((): void => {
    resetCreate();
    resetUpdate();
    setParams({});
  }, [resetCreate, resetUpdate, setParams]);

  const openKey =
    openForm === null ? null : openForm.mode === 'new' ? 'new' : `edit-${openForm.id}`;
  const formRef = usePanelFocus(openKey, handleClose, newRef);

  const handleNew = (): void => {
    create.reset();
    setNotice(null);
    setParams({ new: '' });
  };

  // The name is a link, which opens the form through the address; this clears what
  // the last form left behind.
  const handleEdit = (): void => {
    update.reset();
    setNotice(null);
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
      minWidth: '12rem',
      isIdentity: true,
      render: (template) => (
        <Link
          to={{ search: `?edit=${template.id}` }}
          aria-label={`Edit ${template.name}`}
          onClick={handleEdit}
        >
          {template.name}
        </Link>
      ),
      sortValue: (template) => template.name.toLowerCase(),
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '10rem',
      isActions: true,
      render: (template) => (
        <span className="cluster cluster--nowrap">
          <DeleteButton
            label={`Delete ${template.name}`}
            disabled={remove.isPending}
            onDelete={() => handleDelete(template)}
          />
        </span>
      ),
    },
    {
      key: 'subject',
      header: 'Subject',
      minWidth: '12rem',
      dropOrder: DROP_ORDER.subject,
      render: (template) => (template.subject === '' ? '—' : <FieldText text={template.subject} />),
    },
    {
      key: 'email_type_name',
      header: 'Type',
      width: '7rem',
      dropOrder: DROP_ORDER.type,
      render: (template) => template.email_type_name || '—',
      sortValue: (template) => template.email_type_name,
    },
    {
      key: 'updated_at',
      header: 'Last edited',
      width: '7rem',
      noWrap: true,
      dropOrder: DROP_ORDER.lastEdited,
      render: (template) => <DateText value={template.updated_at} />,
      sortValue: (template) => template.updated_at,
    },
  ];

  return (
    <Page
      title="Templates"
      lede="Messages you send again and again, such as the monthly newsletter. Start a draft from one on the compose screen; changing the draft leaves the template as it is."
      actions={
        openForm === null ? (
          <Button ref={newRef} onClick={handleNew}>
            New template
          </Button>
        ) : null
      }
    >
      <div ref={formRef} className="bulk-email__form-slot">
        {openForm?.mode === 'new' ? (
          <Card eyebrow="New" title="New template">
            <TemplateForm
              submitLabel="Add template"
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
              submitLabel="Save changes"
              pending={update.isPending}
              error={update.error}
              onSubmit={(input) => handleUpdate(editing.id, input)}
              onCancel={handleClose}
            />
          </Card>
        )}
      </div>

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
            The templates didn&apos;t load. Try again in a moment.
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
            emptyAction={
              openForm === null ? (
                <Button variant="secondary" onClick={handleNew}>
                  New template
                </Button>
              ) : undefined
            }
            isLoading={templates.isLoading}
          />
        )}
      </Card>
    </Page>
  );
}
