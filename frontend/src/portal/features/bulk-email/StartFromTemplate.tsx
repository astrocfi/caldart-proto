/**
 * The template controls at the top of **What it says**: **Start from a template**
 * fills the draft from a saved template, and **Save as a template** keeps the draft's
 * words as one.
 *
 * Starting from a template replaces the subject and the message, and the type when
 * the template has one; the people in the batch stay. When the draft already has
 * words, it asks before it replaces them. The draft is a copy: changing it leaves the
 * template as it is. Templates are CalDART management's, so nobody else sees either
 * control.
 */
import { useId, useState } from 'react';
import type { FormEvent, JSX } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/portal/api/client';
import type { BulkEmailDetail, EmailTemplate } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { Field } from '@/portal/components/Field';
import { PanelButton } from '@/portal/components/PanelButton';
import { useToast } from '@/portal/components/Toast';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { hasAnyRole } from '@/portal/nav';
import { emailKey } from './api';
import { TYPE_CHANGED_MESSAGE, wasUnqueued } from './EmailTypeChoice';
import { useApplyTemplate, useCreateTemplate, useTemplates } from './reuseApi';

/** What the confirmation says before a template replaces words already written. */
export const REPLACE_WARNING =
  "This replaces the subject and the message you have written with the template's. The people in the batch stay.";

/** What a failed request says when the server gave no sentence of its own. */
const FALLBACK_ERROR = 'That did not work. Try again.';

/**
 * Whether a draft holds any words or pictures: a subject, or a message with text or
 * an image once its tags are taken away.
 */
export function hasWords(subject: string, body: string): boolean {
  const content = body.replace(/<(?!img\b)[^>]*>/gi, '').trim();
  return subject.trim() !== '' || content !== '';
}

export interface TemplateControlsProps {
  emailId: number;
  /** The words on the screen now, which may be ahead of the saved ones. */
  subject: string;
  body: string;
  /** The draft's type and Reply-To as saved, which **Save as a template** keeps too. */
  emailType: number | null;
  replyTo: string;
  /** Save the words on the screen first; resolves true once they are saved. */
  onBeforeReplace: () => Promise<boolean>;
  /** Called once the template's words are saved in the draft, to show them. */
  onReplaced: () => void;
}

/** Both template controls, side by side; nothing for a sender who is not management. */
export function TemplateControls(props: TemplateControlsProps): JSX.Element | null {
  const { roles } = useAuth();
  const [savedName, setSavedName] = useState<string | null>(null);
  if (!hasAnyRole(roles, ['management'])) return null;
  return (
    <div className="stack-tight">
      <div className="cluster">
        <PanelButton label="Start from a template" legend="Start from a template">
          {() => <StartFromTemplate {...props} />}
        </PanelButton>
        <PanelButton label="Save as a template" legend="Save as a template">
          {(handleClose) => (
            <SaveAsTemplate
              {...props}
              onSaved={(name) => {
                handleClose();
                setSavedName(name);
              }}
            />
          )}
        </PanelButton>
      </div>
      {savedName === null ? null : (
        <p role="status">{`Saved as the template ${savedName}. Find it under Templates.`}</p>
      )}
    </div>
  );
}

/** The template picker, and the button that fills the draft from the one chosen. */
function StartFromTemplate({
  emailId,
  subject,
  body,
  onBeforeReplace,
  onReplaced,
}: TemplateControlsProps): JSX.Element {
  const templates = useTemplates();
  const apply = useApplyTemplate(emailId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [chosen, setChosen] = useState('');
  const id = useId();

  if (templates.isPending) return <p role="status">Loading the templates…</p>;
  if (templates.isError) {
    return (
      <p className="field__error" role="alert">
        The templates could not be loaded.
      </p>
    );
  }
  if (templates.data.length === 0) {
    return (
      <p className="muted">
        No templates are saved yet. Write a message, then press Save as a template.
      </p>
    );
  }

  const template: EmailTemplate | undefined = templates.data.find(
    (option) => String(option.id) === chosen,
  );
  const handleUse = async (): Promise<void> => {
    if (template === undefined) return;
    if (!(await onBeforeReplace())) throw new Error('The draft is not saved yet.');
    const before = queryClient.getQueryData<BulkEmailDetail>(emailKey(emailId));
    const filled = await apply.mutateAsync(template.id);
    if (wasUnqueued(before, filled)) toast.show(TYPE_CHANGED_MESSAGE, 'info');
    onReplaced();
  };

  return (
    <div className="stack-tight">
      <div className="field">
        <label className="field__label" htmlFor={id}>
          Template
        </label>
        <select id={id} value={chosen} onChange={(change) => setChosen(change.target.value)}>
          <option value="">Choose a template</option>
          {templates.data.map((option) => (
            <option key={option.id} value={String(option.id)}>
              {option.name}
            </option>
          ))}
        </select>
      </div>
      {hasWords(subject, body) ? (
        <ConfirmButton
          label="Use this template"
          variant="primary"
          disabled={template === undefined}
          choices={[{ label: 'Replace my words', variant: 'danger', onChoose: handleUse }]}
        >
          <p>{REPLACE_WARNING}</p>
        </ConfirmButton>
      ) : (
        <div>
          <Button
            small
            disabled={template === undefined || apply.isPending}
            onClick={() => void handleUse().catch(() => undefined)}
          >
            Use this template
          </Button>
        </div>
      )}
      {apply.error === null ? null : (
        <p className="field__error" role="alert">
          {apply.error instanceof ApiError ? apply.error.message : FALLBACK_ERROR}
        </p>
      )}
    </div>
  );
}

/** A name, and **Save template**, which keeps the draft's words as a template. */
function SaveAsTemplate({
  subject,
  body,
  emailType,
  replyTo,
  onBeforeReplace,
  onSaved,
}: TemplateControlsProps & { onSaved: (name: string) => void }): JSX.Element {
  const [name, setName] = useState('');
  const create = useCreateTemplate();

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    void onBeforeReplace().then((isSaved) => {
      if (!isSaved) return;
      create.mutate(
        { name, subject, body, email_type: emailType, reply_to: replyTo },
        {
          onSuccess: (template) => onSaved(template.name),
        },
      );
    });
  };

  return (
    <form className="stack-tight" aria-label="Save as a template" onSubmit={handleSubmit}>
      <Field
        label="Template name"
        error={fieldError(create.error, 'name')}
        hint="Such as Monthly newsletter. The subject, message, and type are kept."
        required
      >
        {(props) => (
          <input
            {...props}
            maxLength={80}
            value={name}
            onChange={(change) => setName(change.target.value)}
          />
        )}
      </Field>
      <FormAlert error={create.error} handled={['name']} />
      <div className="cluster">
        <Button type="submit" small disabled={create.isPending}>
          {create.isPending ? 'Saving…' : 'Save template'}
        </Button>
      </div>
    </form>
  );
}
