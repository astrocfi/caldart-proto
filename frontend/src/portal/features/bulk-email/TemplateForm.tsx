/**
 * The form behind **New template** and each row's **Edit** on the Templates screen.
 *
 * It is the compose screen's **What it says** card, saved under a name: the type in
 * the same radio list with each type's description, the subject, the **Reply-To**
 * address with the same sentence naming the default address, and the message in the
 * same rich text editor, with **Insert field** for each person's own details. Nothing saves until **Save
 * template** is pressed. The server checks the name against every other template
 * and the words as it checks a draft's.
 */
import { useId, useRef, useState } from 'react';
import type { FormEvent, JSX } from 'react';

import type { EmailTemplate, EmailTemplateWrite } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { RichTextEditor } from '@/portal/components/RichTextEditor';
import type { RichTextEditorHandle } from '@/portal/components/RichTextEditor';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { useBulkSender, useSendableEmailTypes } from './api';
import { TypeRadios } from './EmailTypeChoice';
import type { TypeOption } from './EmailTypeChoice';
import { InsertFieldMenu } from './InsertFieldMenu';
import { replyToHint } from './ReplyToField';
import { uploadBulkEmailImage, useBulkEmailFields } from './richTextApi';

/** The fields the form shows the server's complaints beside. */
const HANDLED_FIELDS = ['name', 'email_type', 'subject', 'reply_to', 'body'];

/** The longest name and subject the server accepts. */
const NAME_MAX_LENGTH = 80;
const SUBJECT_MAX_LENGTH = 200;

/** The choice of no type, first in the list. */
const NO_TYPE: TypeOption = {
  id: null,
  name: 'No type',
  description: 'Choose the type in each draft started from this template.',
};

export interface TemplateFormProps {
  /** The template to edit; without one the form saves a new template. */
  template?: EmailTemplate;
  /** Shown on the submit button, and the form's name. */
  submitLabel: string;
  pending: boolean;
  /** The last save's error, shown beside its field. */
  error: unknown;
  onSubmit: (input: EmailTemplateWrite) => void;
  onCancel: () => void;
}

/** A template's name, type, subject, Reply-To, and message. */
export function TemplateForm({
  template,
  submitLabel,
  pending,
  error,
  onSubmit: handleSave,
  onCancel: handleCancel,
}: TemplateFormProps): JSX.Element {
  const [name, setName] = useState(template?.name ?? '');
  const [emailType, setEmailType] = useState<number | null>(template?.email_type ?? null);
  const [subject, setSubject] = useState(template?.subject ?? '');
  const [replyTo, setReplyTo] = useState(template?.reply_to ?? '');
  const [body, setBody] = useState(template?.body ?? '');
  const types = useSendableEmailTypes();
  const sender = useBulkSender();
  const fields = useBulkEmailFields();
  const typeError = fieldError(error, 'email_type');
  const typeOptions: TypeOption[] = [
    NO_TYPE,
    ...(types.data ?? []),
    // A type the sender may no longer send stays offered while the template has it.
    ...(template !== undefined &&
    template.email_type !== null &&
    !(types.data ?? []).some((option) => option.id === template.email_type)
      ? [{ id: template.email_type, name: template.email_type_name, description: '' }]
      : []),
  ];
  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<RichTextEditorHandle>(null);
  const messageId = useId();
  const bodyError = fieldError(error, 'body');

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    handleSave({
      name,
      subject,
      body,
      reply_to: replyTo,
      email_type: emailType,
    });
  };

  return (
    <form className="stack" aria-label={submitLabel} onSubmit={handleSubmit}>
      <Field
        label="Name"
        error={fieldError(error, 'name')}
        hint="What the template is called when you choose it, such as Monthly newsletter."
        required
      >
        {(props) => (
          <input
            {...props}
            maxLength={NAME_MAX_LENGTH}
            value={name}
            onChange={(change) => setName(change.target.value)}
          />
        )}
      </Field>
      <fieldset className="stack-tight bulk-email__types">
        <legend>Type of email</legend>
        <p className="field__hint">A draft started from this template takes this type.</p>
        <TypeRadios
          name="template-email-type"
          options={typeOptions}
          chosen={emailType}
          onChoose={(next) => setEmailType(next)}
        />
        {typeError === null ? null : (
          <p className="field__error" role="alert">
            {typeError}
          </p>
        )}
      </fieldset>
      <Field
        label="Subject"
        error={fieldError(error, 'subject')}
        hint="One line that says what it is about."
      >
        {(props) => (
          <input
            {...props}
            ref={subjectRef}
            type="text"
            maxLength={SUBJECT_MAX_LENGTH}
            value={subject}
            onChange={(change) => setSubject(change.target.value)}
          />
        )}
      </Field>
      <Field
        label="Reply-To"
        error={fieldError(error, 'reply_to')}
        hint={replyToHint(sender.data?.default_reply_to ?? '')}
      >
        {(props) => (
          <input
            {...props}
            type="email"
            autoComplete="off"
            placeholder={sender.data?.default_reply_to}
            maxLength={254}
            value={replyTo}
            onChange={(change) => setReplyTo(change.target.value)}
          />
        )}
      </Field>
      <div className="field">
        {/* The editing area names itself "Message"; this is the label a reader sees. */}
        <span className="field__label" aria-hidden="true">
          Message
        </span>
        <RichTextEditor
          ref={editorRef}
          label="Message"
          value={body}
          onChange={(next) => setBody(next)}
          onUploadImage={(file) => uploadBulkEmailImage(file)}
          fields={fields.data}
          describedBy={bodyError === null ? undefined : `${messageId}-error`}
          invalid={bodyError !== null}
          toolbarExtra={
            <InsertFieldMenu
              subjectRef={subjectRef}
              onSubjectChange={(next) => setSubject(next)}
              editorRef={editorRef}
            />
          }
        />
        {bodyError === null ? null : (
          <span className="field__error" id={`${messageId}-error`} role="alert">
            {bodyError}
          </span>
        )}
      </div>
      <FormAlert error={error} handled={HANDLED_FIELDS} />
      <div className="cluster">
        <Button type="submit" disabled={pending}>
          {pending ? 'Saving…' : submitLabel}
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
