/**
 * The **Insert field** menus: one beside the subject puts a recipient field in as its
 * token, such as `{first_name}`, and one in the message's toolbar puts it in as a chip
 * that is written as the same token, so nobody has to type the syntax.  Each person's
 * copy then carries that person's own value.
 */
import type { JSX, RefObject } from 'react';
import { flushSync } from 'react-dom';

import type { BulkEmailField } from '@/portal/api/types';
import { PanelButton } from '@/portal/components/PanelButton';
import type { RichTextEditorHandle } from '@/portal/components/RichTextEditor';

import { useBulkEmailFields } from './richTextApi';
import './insert-field.css';

/** The accessible name of the subject's menu, which says where its field goes. */
export const SUBJECT_MENU_NAME = 'Insert field in the subject';

/** The token a field is written as: its name in braces. */
function tokenText(field: BulkEmailField): string {
  return `{${field.token}}`;
}

interface InsertFieldMenuProps {
  /** The accessible name, when it must say more than *Insert field*. */
  name?: string;
  /** Puts the chosen field in. */
  onChoose: (field: BulkEmailField) => void;
}

/**
 * A button that opens the list of recipient fields, each by its label with its
 * description, and hands the chosen one to `onChoose`, closing the list.
 */
function InsertFieldMenu({ name, onChoose: handleChoose }: InsertFieldMenuProps): JSX.Element {
  const fields = useBulkEmailFields();
  return (
    <PanelButton label="Insert field" name={name} legend="Fields">
      {(handleClose) => {
        if (fields.isPending) return <p>Loading the fields…</p>;
        if (fields.isError)
          return <p role="alert">The fields didn&apos;t load. Try again in a moment.</p>;
        return (
          <ul className="insert-field__list">
            {fields.data.map((field) => (
              <li key={field.token}>
                <button
                  type="button"
                  className="insert-field__choice"
                  onClick={() => {
                    handleChoose(field);
                    handleClose();
                  }}
                >
                  <span className="insert-field__label">{field.label}</span>
                  <span className="insert-field__description">{field.description}</span>
                </button>
              </li>
            ))}
          </ul>
        );
      }}
    </PanelButton>
  );
}

export interface SubjectFieldMenuProps {
  /** The subject input. */
  subjectRef: RefObject<HTMLInputElement | null>;
  /** Receives the subject with the token put in. */
  onSubjectChange: (subject: string) => void;
}

/**
 * The subject's **Insert field**: puts the chosen field's token into the subject at
 * the cursor, replacing any selected text, and leaves the cursor just after it.
 */
export function SubjectFieldMenu({
  subjectRef,
  onSubjectChange,
}: SubjectFieldMenuProps): JSX.Element {
  const handleChoose = (field: BulkEmailField): void => {
    const subject = subjectRef.current;
    if (subject === null) return;
    const text = tokenText(field);
    const start = subject.selectionStart ?? subject.value.length;
    const end = subject.selectionEnd ?? start;
    // Committed at once, so the caret can be placed in the input's new value.
    flushSync(() =>
      onSubjectChange(subject.value.slice(0, start) + text + subject.value.slice(end)),
    );
    subject.focus();
    subject.setSelectionRange(start + text.length, start + text.length);
  };
  return <InsertFieldMenu name={SUBJECT_MENU_NAME} onChoose={handleChoose} />;
}

export interface MessageFieldMenuProps {
  /** The message's editor. */
  editorRef: RefObject<RichTextEditorHandle | null>;
}

/**
 * The message's **Insert field**, in the editor's toolbar: puts the chosen field in
 * at the cursor as a chip (`RichTextEditorHandle.insertField`).
 */
export function MessageFieldMenu({ editorRef }: MessageFieldMenuProps): JSX.Element {
  return <InsertFieldMenu onChoose={(field) => editorRef.current?.insertField(field.token)} />;
}
