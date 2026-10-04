/**
 * The **Insert field** menu: puts a recipient field into the subject, as its token
 * such as `{first_name}`, or into the message, as a chip that is written as the same
 * token, so nobody has to type the syntax.  Each person's copy then carries that
 * person's own value.
 */
import { useEffect, useRef } from 'react';
import type { JSX, RefObject } from 'react';
import { flushSync } from 'react-dom';

import type { BulkEmailField } from '@/portal/api/types';
import { PanelButton } from '@/portal/components/PanelButton';
import type { RichTextEditorHandle } from '@/portal/components/RichTextEditor';

import { useBulkEmailFields } from './richTextApi';
import './insert-field.css';

/** Where the next field goes: the one of the two that had the focus last. */
type Target = 'subject' | 'editor';

export interface InsertFieldMenuProps {
  /** The subject input. */
  subjectRef: RefObject<HTMLInputElement | null>;
  /** Receives the subject with the token put in. */
  onSubjectChange: (subject: string) => void;
  /** The message's editor. */
  editorRef: RefObject<RichTextEditorHandle | null>;
}

/** The token a field is written as: its name in braces. */
export function tokenText(field: BulkEmailField): string {
  return `{${field.token}}`;
}

/**
 * A button that opens the list of recipient fields, each by its label with its
 * description, and puts the chosen one in at the cursor.
 *
 * The field goes into whichever of the subject and the message had the focus
 * last, the message until either has: the subject gets its token as text, the
 * message a chip (`RichTextEditorHandle.insertField`).  It replaces any selected
 * text, and the cursor ends up just after it.
 */
export function InsertFieldMenu({
  subjectRef,
  onSubjectChange,
  editorRef,
}: InsertFieldMenuProps): JSX.Element {
  const fields = useBulkEmailFields();
  const target = useRef<Target>('editor');

  useEffect(() => {
    const handleFocusIn = (event: FocusEvent): void => {
      const node = event.target instanceof Node ? event.target : null;
      if (node !== null && node === subjectRef.current) target.current = 'subject';
      else if (editorRef.current?.contains(node) === true) target.current = 'editor';
    };
    document.addEventListener('focusin', handleFocusIn);
    return () => document.removeEventListener('focusin', handleFocusIn);
  }, [subjectRef, editorRef]);

  const insert = (field: BulkEmailField): void => {
    const subject = subjectRef.current;
    if (target.current === 'editor' || subject === null) {
      editorRef.current?.insertField(field.token);
      return;
    }
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

  return (
    <PanelButton label="Insert field" legend="Fields">
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
                    insert(field);
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
